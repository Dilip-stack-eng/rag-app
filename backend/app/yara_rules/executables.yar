rule Embedded_Windows_PE
{
    meta:
        description = "Windows PE (MZ/PE) executable header found in file content"
        severity = "high"

    condition:
        uint16(0) == 0x5A4D
}

rule Embedded_ELF_Binary
{
    meta:
        description = "Linux ELF executable header found in file content"
        severity = "high"

    condition:
        uint32(0) == 0x464C457F
}

rule Embedded_MachO_Binary
{
    meta:
        description = "macOS Mach-O executable header found in file content"
        severity = "high"

    condition:
        uint32(0) == 0xFEEDFACE or uint32(0) == 0xFEEDFACF or
        uint32(0) == 0xCEFAEDFE or uint32(0) == 0xCFFAEDFE
}
