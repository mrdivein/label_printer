"""ProfileController: save / load / delete printer profiles (paper, compensation, print quality)."""
from PySide6.QtCore import Property, QObject, Signal, Slot

from ..services.profile_service import ProfileService


class ProfileController(QObject):
    namesChanged = Signal()
    message = Signal(str)

    def __init__(self, service: ProfileService, document, printing, parent=None):
        super().__init__(parent)
        self.service = service
        self.document = document
        self.printing = printing

    def _get_names(self):
        return self.service.names()

    names = Property('QStringList', _get_names, notify=namesChanged)

    @Slot(str, result=str)
    def save(self, name):
        try:
            saved = self.service.save(name, self.document.cfg, self.printing.printer)
        except Exception as e:
            return str(e)
        self.namesChanged.emit()
        self.message.emit(f'Đã lưu hồ sơ máy in: {saved}')
        return ''

    @Slot(str, result=str)
    def load(self, name):
        profile = self.service.get(name)
        if profile is None:
            return 'Profile not found.'
        self.document.apply_profile(profile)
        if profile.get('printer') and profile['printer'] in self.printing.printers:
            self.printing.printer = profile['printer']
        self.message.emit(f'Đã nạp hồ sơ máy in: {name}')
        return ''

    @Slot(str)
    def delete(self, name):
        self.service.delete(name)
        self.namesChanged.emit()
