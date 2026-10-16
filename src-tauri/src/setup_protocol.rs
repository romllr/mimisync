pub fn decode(bytes: &[u8]) -> String {
    decode_as(
        bytes,
        bytes.starts_with(&[0xff, 0xfe]) || bytes.iter().take(80).any(|b| *b == 0),
    )
}
fn decode_as(bytes: &[u8], utf16: bool) -> String {
    if utf16 {
        let utf16: Vec<u16> = bytes
            .chunks_exact(2)
            .map(|x| u16::from_le_bytes([x[0], x[1]]))
            .collect();
        String::from_utf16_lossy(&utf16)
            .trim_start_matches('\u{feff}')
            .to_owned()
    } else {
        String::from_utf8_lossy(bytes)
            .trim_start_matches('\u{feff}')
            .to_owned()
    }
}
/// WSL writes UTF-16LE when redirected; Linux commands normally write UTF-8.
/// Keep partial code units/lines across reads and never drop the stream on a
/// non-UTF-8 byte, as BufRead::lines would do.
pub fn read_log_stream(
    mut reader: impl std::io::Read,
    mut emit: impl FnMut(String),
) -> std::io::Result<()> {
    let mut pending = Vec::new();
    let mut encoding = None;
    let mut chunk = [0u8; 8192];
    loop {
        let count = reader.read(&mut chunk)?;
        pending.extend_from_slice(&chunk[..count]);
        if encoding.is_none() && (pending.len() >= 2 || count == 0) {
            encoding = Some(
                pending.starts_with(&[0xff, 0xfe]) || pending.iter().take(80).any(|b| *b == 0),
            );
        }
        if let Some(utf16) = encoding {
            loop {
                let end = if utf16 {
                    pending
                        .chunks_exact(2)
                        .position(|p| p == [10, 0])
                        .map(|i| i * 2 + 2)
                } else {
                    pending.iter().position(|b| *b == 10).map(|i| i + 1)
                };
                let Some(end) = end else { break };
                let line: Vec<_> = pending.drain(..end).collect();
                let text = decode_as(&line, utf16)
                    .trim_end_matches(['\r', '\n'])
                    .to_owned();
                if !text.is_empty() {
                    emit(text);
                }
            }
            if count == 0 && !pending.is_empty() {
                emit(
                    decode_as(&pending, utf16)
                        .trim_end_matches(['\r', '\n'])
                        .to_owned(),
                );
            }
        }
        if count == 0 {
            return Ok(());
        }
    }
}
pub fn checksum(text: &str, name: &str) -> Result<String, String> {
    text.lines()
        .find_map(|line| {
            let mut parts = line.split_whitespace();
            let hash = parts.next()?;
            let file = parts.next()?.trim_start_matches('*');
            if file == name && hash.len() == 64 && hash.bytes().all(|b| b.is_ascii_hexdigit()) {
                Some(hash.to_ascii_lowercase())
            } else {
                None
            }
        })
        .ok_or_else(|| "Checksum oficial não encontrado para a imagem Ubuntu.".into())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wsl_utf16_output() {
        let data: Vec<u8> = "\u{feff}Mimisync-Ubuntu\r\n"
            .encode_utf16()
            .flat_map(u16::to_le_bytes)
            .collect();
        assert_eq!(decode(&data).trim(), "Mimisync-Ubuntu");
        assert_eq!(decode(b"Ubuntu\n").trim(), "Ubuntu");
    }
    #[test]
    fn wsl_error_survives_split_utf16_and_unterminated_line() {
        struct Tiny(std::io::Cursor<Vec<u8>>);
        impl std::io::Read for Tiny {
            fn read(&mut self, target: &mut [u8]) -> std::io::Result<usize> {
                let length = target.len().min(3);
                std::io::Read::read(&mut self.0, &mut target[..length])
            }
        }
        let error = "\u{feff}Não foi possível iniciar.\r\nWsl/Service/0x80370102";
        let bytes = error.encode_utf16().flat_map(u16::to_le_bytes).collect();
        let mut logs = Vec::new();
        read_log_stream(Tiny(std::io::Cursor::new(bytes)), |s| logs.push(s)).unwrap();
        assert_eq!(
            logs,
            ["Não foi possível iniciar.", "Wsl/Service/0x80370102"]
        );
        let mut utf8 = Vec::new();
        read_log_stream(&b"apt ready\ninvalid: \xff\nnext line"[..], |s| {
            utf8.push(s)
        })
        .unwrap();
        assert_eq!(utf8, ["apt ready", "invalid: \u{fffd}", "next line"]);
    }
    #[test]
    fn checksum_requires_exact_filename_and_valid_digest() {
        let hash = "a".repeat(64);
        assert_eq!(
            checksum(&format!("{hash} *image.tar.gz\n"), "image.tar.gz").unwrap(),
            hash
        );
        assert!(checksum("bad *image.tar.gz", "image.tar.gz").is_err());
        assert!(checksum(&format!("{hash} *different.tar.gz"), "image.tar.gz").is_err());
        assert!(checksum(&format!("{} *image.tar.gz", "z".repeat(64)), "image.tar.gz").is_err());
    }
}
