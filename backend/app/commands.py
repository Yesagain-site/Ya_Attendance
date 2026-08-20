"""
ADMS command bodies (Phase 5). Each returns the command WITHOUT the "C:<id>:"
prefix — the ADMS getrequest handler adds "C:<device_command.id>:" at dispatch,
so the id the device reports back maps straight to our row.
"""


def user_body(emp: dict) -> str:
    name = (emp.get("name") or emp["pin"]).replace("\t", " ")
    pri = emp.get("privilege") or 0
    card = emp.get("card") or ""
    return (f"DATA USER PIN={emp['pin']}\tName={name}\tPri={pri}\tPasswd=\t"
            f"Card={card}\t\tGrp=1\tVerify=0")


def biodata_body(t: dict) -> str:
    return (f"DATA UPDATE BIODATA Pin={t['pin']}\tNo={t['bio_no']}\t"
            f"Index={t['bio_index']}\tValid={t['valid']}\tDuress=0\t"
            f"Type={t['bio_type']}\tMajorVer={t['major_ver']}\t"
            f"MinorVer={t['minor_ver']}\tFormat={t['bio_format']}\tTmp={t['template']}")


def delete_user_body(pin: str) -> str:
    return f"DATA DELETE USERINFO PIN={pin}"


# Whitelisted device-menu commands (safe subset).
MENU = {
    "INFO": "INFO",
    "REBOOT": "REBOOT",
    "CHECK": "CHECK",              # ask device to re-sync data
    "CLEAR_LOG": "CLEAR LOG",      # clears the device's own transaction log
    "CLEAR_PHOTO": "CLEAR PHOTO",
}


def menu_body(key: str) -> str | None:
    return MENU.get(key)
