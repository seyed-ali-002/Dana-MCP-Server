use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{AppHandle, Manager, RunEvent};

static SETUP_AGENT: Mutex<Option<Child>> = Mutex::new(None);

fn find_project_root() -> Option<std::path::PathBuf> {
    let candidates = [
        std::env::var_os("DANA_ROOT").map(std::path::PathBuf::from),
        std::env::current_dir().ok(),
        std::env::current_exe().ok().and_then(|p| p.parent().map(|x| x.to_path_buf())),
    ];
    for candidate in candidates.into_iter().flatten() {
        for root in candidate.ancestors() {
            if root.join("dana").join("setup_service.py").exists() {
                return Some(root.to_path_buf());
            }
        }
    }
    None
}

fn python_command(root: &std::path::Path) -> Option<(String, Vec<String>)> {
    let python = if cfg!(windows) {
        root.join(".venv").join("Scripts").join("python.exe")
    } else {
        root.join(".venv").join("bin").join("python")
    };
    if python.exists() {
        return Some((python.to_string_lossy().into_owned(), vec![]));
    }
    for candidate in if cfg!(windows) { vec!["py", "python"] } else { vec!["python3", "python"] } {
        if Command::new(candidate).arg("--version").output().is_ok() {
            return Some((candidate.to_string(), if candidate == "py" { vec!["-3".into()] } else { vec![] }));
        }
    }
    None
}

#[tauri::command]
fn start_setup_service(app: AppHandle) -> Result<u16, String> {
    if let Some(child) = SETUP_AGENT.lock().map_err(|e| e.to_string())?.as_mut() {
        if child.try_wait().map_err(|e| e.to_string())?.is_none() {
            return Err("Dana setup service is already running without a known port.".into());
        }
    }

    let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
    let bundled = if cfg!(windows) {
        resource_dir.join("dana-agent.exe")
    } else {
        resource_dir.join("dana-agent")
    };

    let mut command = if bundled.exists() {
        Command::new(bundled)
    } else {
        let root = find_project_root().ok_or("Dana project root was not found. Set DANA_ROOT for development.")?;
        let (python, prefix) = python_command(&root).ok_or("Python runtime was not found.")?;
        let mut cmd = Command::new(python);
        for arg in prefix { cmd.arg(arg); }
        cmd.arg("-m").arg("dana.setup_service").current_dir(root);
        cmd
    };

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command.stdout(Stdio::piped()).stderr(Stdio::null());
    let mut child = command.spawn().map_err(|e| format!("Could not start setup service: {e}"))?;
    let stdout = child.stdout.take().ok_or("Setup service did not expose stdout.")?;
    let mut reader = BufReader::new(stdout);
    let mut line = String::new();
    reader.read_line(&mut line).map_err(|e| format!("Could not read setup service port: {e}"))?;
    let port: u16 = line.trim().parse().map_err(|_| format!("Invalid setup service port: {}", line.trim()))?;

    *SETUP_AGENT.lock().map_err(|e| e.to_string())? = Some(child);
    Ok(port)
}

fn stop_setup_service() {
    if let Ok(mut guard) = SETUP_AGENT.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![start_setup_service])
        .build(tauri::generate_context!())
        .expect("error while building Dana")
        .run(|_app, event| {
            if matches!(event, RunEvent::Exit) {
                stop_setup_service();
            }
        });
}
