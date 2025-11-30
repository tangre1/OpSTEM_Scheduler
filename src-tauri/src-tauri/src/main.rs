// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Stdio};

fn main() {
    // Start FastAPI backend
    let _backend = Command::new("python3")
        .arg("../../main.py")
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("failed to start FastAPI backend");

    // Start the Tauri app
    src_tauri_lib::run()
}
