from threatintel.iocs import extract_iocs, ioc_summary

SAMPLE = (
    "CVE-2024-1234 is exploited in the wild. The malware contacts 203.0.113.7 "
    "and 10.0.0.5 as well as c2.evil-domain.com. "
    "MD5 d41d8cd98f00b204e9800998ecf8427e "
    "SHA256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855. "
    "Downloaded from https://evil-domain.com/payload or contact attacker@evil-domain.com"
)


def test_extract_common_iocs():
    iocs = extract_iocs(SAMPLE)
    assert "CVE-2024-1234" in iocs["cve"]
    assert "203.0.113.7" in iocs["ipv4"]
    assert "evil-domain.com" in iocs["domain"]
    assert "d41d8cd98f00b204e9800998ecf8427e" in iocs["md5"]
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in iocs["sha256"]
    assert any("evil-domain.com/payload" in u for u in iocs["url"])
    assert "attacker@evil-domain.com" in iocs["email"]


def test_private_ips_excluded_by_default():
    iocs = extract_iocs("Scan from 10.0.0.5 and 192.168.1.1 hit 8.8.8.8")
    assert "10.0.0.5" not in iocs.get("ipv4", [])
    assert "192.168.1.1" not in iocs.get("ipv4", [])
    assert "8.8.8.8" in iocs["ipv4"]


def test_no_duplicate_hash_classification():
    iocs = extract_iocs("hash e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert "sha256" in iocs
    assert "md5" not in iocs
    assert "sha1" not in iocs


def test_empty_and_summary():
    assert extract_iocs("") == {}
    iocs = extract_iocs("CVE-2023-1111 and CVE-2023-2222")
    assert ioc_summary(iocs) == "cve: 2"
