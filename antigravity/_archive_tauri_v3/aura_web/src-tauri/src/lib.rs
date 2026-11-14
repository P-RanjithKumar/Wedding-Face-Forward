use tauri_plugin_shell::ShellExt;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .plugin(
      tauri_plugin_log::Builder::default()
        .level(log::LevelFilter::Info)
        .targets([
            tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::Stdout),
            tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::LogDir {
                file_name: Some("aura".to_string()),
            }),
            tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::Webview),
        ])
        .build(),
    )
    .setup(|app| {
      let shell = app.shell();
      
      let sidecar_name = "aura-backend";
      log::info!("Starting AURA with sidecar: {}", sidecar_name);

      // Start FastAPI server
      match shell.sidecar(sidecar_name) {
        Ok(cmd) => {
          match cmd.args(["--run-server"]).spawn() {
            Ok(_) => log::info!("Server sidecar spawned successfully"),
            Err(e) => log::error!("Failed to spawn server sidecar: {}", e),
          }
        },
        Err(e) => log::error!("Failed to create server sidecar command: {}", e),
      }

      // Start Worker
      match shell.sidecar(sidecar_name) {
        Ok(cmd) => {
          match cmd.args(["--run-worker"]).spawn() {
            Ok(_) => log::info!("Worker sidecar spawned successfully"),
            Err(e) => log::error!("Failed to spawn worker sidecar: {}", e),
          }
        },
        Err(e) => log::error!("Failed to create worker sidecar command: {}", e),
      }

      // Start WhatsApp sender
      match shell.sidecar(sidecar_name) {
        Ok(cmd) => {
          match cmd.args(["--run-whatsapp"]).spawn() {
            Ok(_) => log::info!("WhatsApp sidecar spawned successfully"),
            Err(e) => log::error!("Failed to spawn whatsapp sidecar: {}", e),
          }
        },
        Err(e) => log::error!("Failed to create whatsapp sidecar command: {}", e),
      }

      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
