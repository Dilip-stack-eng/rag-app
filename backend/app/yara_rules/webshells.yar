rule Generic_PHP_Webshell
{
    meta:
        description = "Common PHP webshell patterns - eval/assert/system on user-controlled superglobals"
        severity = "critical"

    strings:
        $eval_post = "eval($_POST" nocase
        $eval_get = "eval($_GET" nocase
        $eval_req = "eval($_REQUEST" nocase
        $assert_post = "assert($_POST" nocase
        $system_req = "system($_REQUEST" nocase
        $passthru = "passthru($_" nocase
        $base64eval = "eval(base64_decode(" nocase

    condition:
        any of them
}

rule Known_Webshell_Markers
{
    meta:
        description = "Filename/banner markers used by well-known public webshell kits"
        severity = "critical"

    strings:
        $c99 = "c99shell" nocase
        $r57 = "r57shell" nocase
        $wso = "WSO Shell" nocase
        $filesman = "FilesMan" nocase
        $b374k = "b374k" nocase
        $antichat = "AnonymousFox" nocase

    condition:
        any of them
}

rule Generic_JSP_ASPX_Webshell
{
    meta:
        description = "JSP/ASPX command-execution webshell patterns"
        severity = "critical"

    strings:
        $jsp1 = "Runtime.getRuntime().exec(" nocase
        $jsp2 = "ProcessBuilder(" nocase
        $aspx1 = "eval request(" nocase
        $aspx2 = "Response.Write" nocase

    condition:
        any of ($jsp1, $jsp2) or all of ($aspx1, $aspx2)
}
