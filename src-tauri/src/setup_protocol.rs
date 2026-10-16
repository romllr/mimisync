pub fn decode(bytes: &[u8]) -> String {
    if bytes.iter().take(80).any(|b| *b == 0) {
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
