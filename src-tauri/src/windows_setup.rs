//! Ask Windows to install its own WSL component, without an intermediate shell.
use std::{ffi::OsString, os::windows::ffi::OsStringExt};
use windows_sys::Win32::{
    Foundation::{CloseHandle, WAIT_OBJECT_0},
    System::{
        Com::{CoInitializeEx, CoUninitialize, COINIT_APARTMENTTHREADED, COINIT_DISABLE_OLE1DDE},
        SystemInformation::GetSystemDirectoryW,
        Threading::{GetExitCodeProcess, WaitForSingleObject, INFINITE},
    },
    UI::{
        Shell::{ShellExecuteExW, SEE_MASK_NOASYNC, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW},
        WindowsAndMessaging::SW_SHOWNORMAL,
    },
};

struct ComApartment;
impl Drop for ComApartment {
    fn drop(&mut self) {
        unsafe { CoUninitialize() };
    }
}

pub fn install_wsl() -> Result<(), String> {
    // This function runs on a new dedicated worker; balance both S_OK and S_FALSE.
    let initialized = unsafe {
        CoInitializeEx(
            std::ptr::null(),
            (COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE) as u32,
        )
    };
    if initialized < 0 {
        return Err(format!(
            "Não foi possível preparar a instalação Windows: {initialized:#x}"
        ));
    }
    let _apartment = ComApartment;
    let mut directory = vec![0u16; 32768];
    // The buffer is writable and its size is supplied in UTF-16 code units.
    let length = unsafe { GetSystemDirectoryW(directory.as_mut_ptr(), directory.len() as u32) };
    if length == 0 || length as usize >= directory.len() {
        return Err(format!(
            "Não foi possível localizar o Windows: {}",
            std::io::Error::last_os_error()
        ));
    }
    let file = std::path::PathBuf::from(OsString::from_wide(&directory[..length as usize]))
        .join("wsl.exe");
    use std::os::windows::ffi::OsStrExt;
    let file: Vec<u16> = file.as_os_str().encode_wide().chain(Some(0)).collect();
    let verb: Vec<u16> = "runas\0".encode_utf16().collect();
    let args: Vec<u16> = "--install --no-distribution\0".encode_utf16().collect();
    let mut info = SHELLEXECUTEINFOW {
        cbSize: std::mem::size_of::<SHELLEXECUTEINFOW>() as u32,
        fMask: SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC,
        lpVerb: verb.as_ptr(),
        lpFile: file.as_ptr(),
        lpParameters: args.as_ptr(),
        nShow: SW_SHOWNORMAL,
        ..Default::default()
    };
    // All strings remain alive until ShellExecuteExW returns. Windows owns UAC.
    if unsafe { ShellExecuteExW(&mut info) } == 0 {
        let error = std::io::Error::last_os_error();
        return Err(if error.raw_os_error() == Some(1223) {
            "A autorização de administrador foi cancelada. Você pode tentar novamente pelo app."
                .into()
        } else {
            format!("O Windows não conseguiu iniciar a instalação do WSL: {error}")
        });
    }
    if info.hProcess.is_null() {
        return Err(
            "O Windows não forneceu o processo da instalação; verifique o estado do WSL pelo app."
                .into(),
        );
    }
    // Only this worker waits. Close the owned process handle on every outcome.
    let result = unsafe {
        if WaitForSingleObject(info.hProcess, INFINITE) != WAIT_OBJECT_0 {
            Err(format!(
                "Falha ao aguardar a instalação: {}",
                std::io::Error::last_os_error()
            ))
        } else {
            let mut code = 0;
            if GetExitCodeProcess(info.hProcess, &mut code) == 0 {
                Err(format!(
                    "Falha ao consultar a instalação: {}",
                    std::io::Error::last_os_error()
                ))
            } else if matches!(code, 0 | 3010) {
                Ok(())
            } else {
                Err(format!("A instalação do WSL terminou com código {code}."))
            }
        }
    };
    unsafe { CloseHandle(info.hProcess) };
    result
}
