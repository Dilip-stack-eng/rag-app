rule EICAR_Test_File
{
    meta:
        description = "Standard antivirus test file (EICAR) - not real malware, used to verify scanning works"
        severity = "test"

    strings:
        $eicar = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

    condition:
        $eicar
}
