"""Printer profiles persisted in printer_profiles.json (unchanged location and format)."""
from ..core.profiles import profile_from_cfg
from .settings_service import load_profiles, save_profiles


class ProfileService:
    def names(self):
        return sorted(load_profiles().keys())

    def get(self, name):
        return load_profiles().get(name)

    def save(self, name, cfg, printer=""):
        name = (name or "").strip()
        if not name:
            raise ValueError("Enter a profile name.")
        data = load_profiles()
        data[name] = profile_from_cfg(cfg, printer)
        save_profiles(data)
        return name

    def delete(self, name):
        data = load_profiles()
        data.pop(name, None)
        save_profiles(data)
