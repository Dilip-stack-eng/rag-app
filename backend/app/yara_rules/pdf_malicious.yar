rule Malicious_PDF_JavaScript
{
    meta:
        description = "PDF embedding auto-run JavaScript - common exploit/phishing delivery mechanism"
        severity = "high"

    strings:
        $js = "/JavaScript" nocase
        $js2 = "/JS" nocase
        $openaction = "/OpenAction" nocase
        $aa = "/AA" nocase

    condition:
        uint32(0) == 0x46445025 and any of ($js, $js2) and any of ($openaction, $aa)
}

rule Malicious_PDF_Launch_Action
{
    meta:
        description = "PDF /Launch action - can execute an external command/file when opened"
        severity = "critical"

    strings:
        $launch = "/Launch" nocase

    condition:
        uint32(0) == 0x46445025 and $launch
}
