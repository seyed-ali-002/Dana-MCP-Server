use std::io::{Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::{atomic::{AtomicBool, Ordering}, Mutex};

use tauri::{AppHandle, Manager, RunEvent};

static SETUP_AGENT: Mutex<Option<Child>> = Mutex::new(None);
static SETUP_PORT: Mutex<Option<u16>> = Mutex::new(None);
static SHUTDOWN_STARTED: AtomicBool = AtomicBool::new(false);

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
    let bundled_candidates = [
        resource_dir.join("dana-agent"),
        resource_dir.join("dana-agent.exe"),
        resource_dir.join("resources").join("dana-agent"),
        resource_dir.join("resources").join("dana-agent.exe"),
        app.path().executable_dir().ok().map(|p| p.join("resources").join("dana-agent")).unwrap_or_default(),
        app.path().executable_dir().ok().map(|p| p.join("resources").join("dana-agent.exe")).unwrap_or_default(),
    ];
    let bundled = bundled_candidates.into_iter().find(|p| p.is_file());

    let mut command = if let Some(bundled) = bundled {
        let mut cmd = Command::new(bundled);
        cmd.current_dir(&resource_dir);
        cmd
    } else {
        let root = find_project_root().ok_or("Dana bundled runtime was not found. Set DANA_ROOT only for source development.")?;
        let (python, prefix) = python_command(&root).ok_or("Python runtime was not found.")?;
        let mut cmd = Command::new(python);
        for arg in prefix { cmd.arg(arg); }
        cmd.arg("-m").arg("dana.setup_service").current_dir(root);
        cmd
    };

    // A file-based handshake is used instead of stdout. Bundled sidecars may
    // emit bootloader/runtime output before application startup, and Windows
    // suppresses console output for GUI-launched processes.
    let port_file = std::env::temp_dir().join(format!("dana-setup-port-{}.txt", std::process::id()));
    let _ = std::fs::remove_file(&port_file);
    command.env("DANA_SETUP_PORT_FILE", &port_file);

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command.stdout(Stdio::null()).stderr(Stdio::null());
    let mut child = command.spawn().map_err(|e| format!("Could not start setup service: {e}"))?;

    let mut port = None;
    for _ in 0..100 {
        if let Ok(contents) = std::fs::read_to_string(&port_file) {
            if let Ok(value) = contents.trim().parse::<u16>() {
                if value != 0 {
                    port = Some(value);
                    break;
                }
            }
        }
        if let Some(status) = child.try_wait().map_err(|e| format!("Could not check setup service: {e}"))? {
            let _ = std::fs::remove_file(&port_file);
            return Err(format!("Setup service exited before announcing its port (status: {status})."));
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    }

    let _ = std::fs::remove_file(&port_file);
    let port = port.ok_or_else(|| {
        let _ = child.kill();
        format!("Invalid setup service port. Setup service did not start its local API within 5 seconds.")
    })?;

    *SETUP_PORT.lock().map_err(|e| e.to_string())? = Some(port);
    *SETUP_AGENT.lock().map_err(|e| e.to_string())? = Some(child);
    Ok(port)
}

fn stop_dana_before_exit() {
    if SHUTDOWN_STARTED.swap(true, Ordering::SeqCst) {
        return;
    }
    let port = match SETUP_PORT.lock().ok().and_then(|guard| *guard) {
        Some(port) => port,
        None => return,
    };
    if let Ok(mut stream) = TcpStream::connect(("127.0.0.1", port)) {
        let request = format!(
            "POST /api/setup/stop-dana HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            port
        );
        let _ = stream.write_all(request.as_bytes());
        let _ = stream.flush();
        let mut response = Vec::new();
        let _ = stream.read_to_end(&mut response);
    }
}

fn stop_setup_service() {
    if let Ok(mut guard) = SETUP_AGENT.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
    if let Ok(mut port) = SETUP_PORT.lock() {
        *port = None;
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
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                stop_dana_before_exit();
                stop_setup_service();
            }
        });
}
