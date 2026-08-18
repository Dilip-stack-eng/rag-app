rule Suspicious_PowerShell_Download_Exec
{
    meta:
        description = "PowerShell encoded command or download-and-execute pattern, common in droppers embedded in documents"
        severity = "high"

    strings:
        $enc1 = "-EncodedCommand" nocase
        $enc2 = "-enc " nocase
        $dl1 = "DownloadString" nocase
        $dl2 = "DownloadFile" nocase
        $iex = "IEX" nocase
        $invoke = "Invoke-Expression" nocase
        $webclient = "Net.WebClient" nocase
        $bypass = "-ExecutionPolicy Bypass" nocase

    condition:
        2 of them
}

rule Suspicious_LOLBin_Execution
{
    meta:
        description = "Living-off-the-land binary invocation typical of malicious macros/scripts (certutil, mshta, regsvr32, wscript)"
        severity = "high"

    strings:
        $certutil = "certutil" nocase
        $decode = "-decode" nocase
        $mshta = "mshta" nocase
        $regsvr = "regsvr32" nocase
        $wscript = "Wscript.Shell" nocase
        $cmdc = "cmd.exe /c" nocase
        $rundll = "rundll32" nocase

    condition:
        any of ($mshta, $wscript, $rundll) or ($certutil and $decode) or ($regsvr and $cmdc)
}

rule Suspicious_Macro_AutoExec
{
    meta:
        description = "Office macro auto-run trigger combined with shell execution - classic malicious macro pattern"
        severity = "high"

    strings:
        $auto1 = "AutoOpen" nocase
        $auto2 = "AutoExec" nocase
        $auto3 = "Document_Open" nocase
        $auto4 = "Workbook_Open" nocase
        $shell1 = "Shell(" nocase
        $shell2 = "CreateObject(\"WScript.Shell\")" nocase

    condition:
        any of ($auto1, $auto2, $auto3, $auto4) and any of ($shell1, $shell2)
}
