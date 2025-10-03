
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class SettingsDialog:
    def __init__(self, parent):
        # Costruisce il dialog dal file Glade
        self.builder = Gtk.Builder()
        self.builder.add_from_file("settings.glade")

        # Ottiene il dialog
        self.dialog = self.builder.get_object("settings_dialog")

        # Imposta finestra genitore
        self.dialog.set_transient_for(parent)
        self.dialog.set_modal(True)

    def show(self):
        response = self.dialog.run()

        if response == Gtk.ResponseType.OK:
            print("Hai premuto OK")
            # Qui potresti leggere dati da entry, combo, etc.
        elif response == Gtk.ResponseType.CANCEL:
            print("Hai premuto Annulla")

        self.dialog.destroy()

