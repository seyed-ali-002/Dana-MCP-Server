use std::io::{Read, Write};
use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::{atomic::{AtomicBool, Ordering}, Mutex};

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, RunEvent, WindowEvent,
};

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
    if let Some(port) = *SETUP_PORT.lock().map_err(|e| e.to_string())? {
        let mut agent = SETUP_AGENT.lock().map_err(|e| e.to_string())?;
        let alive = match agent.as_mut() {
            Some(child) => child.try_wait().map_err(|e| e.to_string())?.is_none(),
            None => false,
        };
        if alive {
            return Ok(port);
        }
        if let Some(mut stale) = agent.take() {
            let _ = stale.kill();
            let _ = stale.wait();
        }
        *SETUP_PORT.lock().map_err(|e| e.to_string())? = None;
    }

    let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
    let mut agent_bins: Vec<std::path::PathBuf> = vec![
        resource_dir.join("dana-agent"),
        resource_dir.join("dana-agent.exe"),
        resource_dir.join("resources").join("dana-agent"),
        resource_dir.join("resources").join("dana-agent.exe"),
        std::path::PathBuf::from("/usr/lib/Dana/dana-agent"),
        std::path::PathBuf::from("/usr/local/lib/Dana/dana-agent"),
    ];
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            agent_bins.push(parent.join("dana-agent"));
            agent_bins.push(parent.join("resources").join("dana-agent"));
            if let Some(grand) = parent.parent() {
                agent_bins.push(grand.join("lib").join("Dana").join("dana-agent"));
            }
        }
    }
    if let Ok(dir) = app.path().executable_dir() {
        agent_bins.push(dir.join("resources").join("dana-agent"));
        agent_bins.push(dir.join("dana-agent"));
    }

    let project_root = find_project_root();
    let mut launchers: Vec<(String, Vec<String>, Option<std::path::PathBuf>, Option<std::path::PathBuf>)> = Vec::new();
    // (program, args, current_dir, PYTHONPATH)

    for bin in agent_bins.into_iter().filter(|p| p.is_file()) {
        launchers.push((bin.to_string_lossy().into_owned(), vec![], Some(resource_dir.clone()), None));
    }

    // Python module fallbacks (source tree, DANA_ROOT, common paths)
    let mut python_roots: Vec<std::path::PathBuf> = Vec::new();
    if let Some(root) = project_root.clone() {
        python_roots.push(root);
    }
    if let Ok(env_root) = std::env::var("DANA_ROOT") {
        python_roots.push(std::path::PathBuf::from(env_root));
    }
    python_roots.push(std::path::PathBuf::from("/mnt/1CEC9AE6EC9ABA0A/Ali/MCP_Server/Dana"));
    python_roots.push(std::path::PathBuf::from("/usr/lib/Dana"));

    for root in python_roots {
        if !root.join("dana").join("setup_service.py").exists() {
            continue;
        }
        if let Some((python, prefix)) = python_command(&root) {
            let mut args = prefix;
            args.push("-m".into());
            args.push("dana.setup_service".into());
            launchers.push((python, args, Some(root.clone()), Some(root)));
        }
    }
    // System-installed dana package (no project root required)
    for candidate in ["python3", "python"] {
        if Command::new(candidate).arg("-c").arg("import dana.setup_service").output().map(|o| o.status.success()).unwrap_or(false) {
            launchers.push((candidate.into(), vec!["-m".into(), "dana.setup_service".into()], None, None));
            break;
        }
    }

    if launchers.is_empty() {
        return Err("Dana setup runtime was not found. Reinstall the package or set DANA_ROOT to the source tree.".into());
    }

    let port_file = std::env::temp_dir().join(format!("dana-setup-port-{}.txt", std::process::id()));
    let log_path = std::env::temp_dir().join(format!("dana-setup-agent-{}.log", std::process::id()));
    let mut last_error = String::from("No launcher succeeded.");

    for (program, args, cwd, pythonpath) in launchers {
        let _ = std::fs::remove_file(&port_file);
        let _ = std::fs::remove_file(&log_path);

        let mut command = Command::new(&program);
        for arg in &args {
            command.arg(arg);
        }
        if let Some(dir) = cwd {
            command.current_dir(dir);
        }
        if let Some(path) = pythonpath {
            let mut pp = path.to_string_lossy().into_owned();
            if let Ok(existing) = std::env::var("PYTHONPATH") {
                if !existing.is_empty() {
                    pp = format!("{pp}:{existing}");
                }
            }
            command.env("PYTHONPATH", pp);
        }
        command.env("DANA_SETUP_PORT_FILE", &port_file);

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000);
        }

        if let (Ok(out), Ok(err)) = (
            std::fs::File::create(&log_path),
            std::fs::OpenOptions::new().create(true).append(true).open(&log_path),
        ) {
            command.stdout(Stdio::from(out)).stderr(Stdio::from(err));
        } else {
            command.stdout(Stdio::null()).stderr(Stdio::null());
        }

        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(e) => {
                last_error = format!("Could not start {program}: {e}");
                continue;
            }
        };

        let mut port = None;
        for _ in 0..120 {
            if let Ok(contents) = std::fs::read_to_string(&port_file) {
                if let Ok(value) = contents.trim().parse::<u16>() {
                    if value != 0 {
                        port = Some(value);
                        break;
                    }
                }
            }
            if let Ok(Some(status)) = child.try_wait() {
                let detail = std::fs::read_to_string(&log_path).unwrap_or_default();
                let tail = detail.trim();
                let tail = if tail.is_empty() {
                    String::new()
                } else {
                    let lines: Vec<&str> = tail.lines().collect();
                    let start = lines.len().saturating_sub(6);
                    format!(" | {}", lines[start..].join(" | "))
                };
                last_error = format!(
                    "Launcher `{program}` exited before announcing its port (status: {status}){tail}"
                );
                port = None;
                break;
            }
            std::thread::sleep(std::time::Duration::from_millis(50));
        }

        if let Some(port) = port {
            let _ = std::fs::remove_file(&port_file);
            *SETUP_PORT.lock().map_err(|e| e.to_string())? = Some(port);
            *SETUP_AGENT.lock().map_err(|e| e.to_string())? = Some(child);
            return Ok(port);
        }

        let _ = child.kill();
        let _ = child.wait();
    }

    let _ = std::fs::remove_file(&port_file);
    Err(last_error)
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
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
        .setup(|app| {
            let show_i = MenuItem::with_id(app, "show", "Show Dana", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &quit_i])?;

            let icon = app
                .default_window_icon()
                .cloned()
                .expect("Dana window icon is required for the tray");

            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .tooltip("Dana · MCP Control Center")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => show_main_window(app),
                    "quit" => {
                        stop_dana_before_exit();
                        stop_setup_service();
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_main_window(tray.app_handle());
                    }
                })
                .build(app)?;

            if let Some(window) = app.get_webview_window("main") {
                let window_handle = window.clone();
                window.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        // Keep Dana in the background via the system tray.
                        api.prevent_close();
                        let _ = window_handle.hide();
                    }
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Dana")
        .run(|_app, event| {
            match event {
                RunEvent::ExitRequested { .. } => {
                    stop_dana_before_exit();
                }
                RunEvent::Exit => {
                    stop_dana_before_exit();
                    stop_setup_service();
                }
                _ => {}
            }
        });
}
