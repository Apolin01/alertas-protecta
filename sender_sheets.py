"""
sender_sheets.py — Inserta alertas en el mismo Google Sheets que usa el Form.

La hoja 'Tabla_Informacion' ya tiene las columnas del Form. El sistema agrega
filas nuevas al final con el mismo formato, más columnas extra de metadatos.
"""

import logging
import gspread
from google.oauth2.service_account import Credentials
from formatter import SHEET_HEADERS
from config import Config

log = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


class SheetsSender:
    def __init__(self, config: Config):
        self.config = config
        self._sheet = None

    def _get_sheet(self):
        if self._sheet:
            return self._sheet
        try:
            creds = Credentials.from_service_account_file(
                self.config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
            )
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(self.config.SPREADSHEET_ID)

            try:
                self._sheet = spreadsheet.worksheet(self.config.SHEET_NAME)
                log.info(f"Hoja '{self.config.SHEET_NAME}' encontrada.")
            except gspread.WorksheetNotFound:
                # Si no existe, la crea con las columnas del Form + extras
                self._sheet = spreadsheet.add_worksheet(
                    title=self.config.SHEET_NAME, rows=10000, cols=len(SHEET_HEADERS)
                )
                self._sheet.append_row(SHEET_HEADERS)
                log.info(f"Hoja '{self.config.SHEET_NAME}' creada con cabeceras.")

            return self._sheet

        except FileNotFoundError:
            log.error(
                "credentials.json no encontrado. "
                "Descárgalo de Google Cloud Console (Service Account) "
                "y ponlo en la raíz del proyecto."
            )
            return None
        except Exception as e:
            log.error(f"Error conectando Google Sheets: {e}")
            return None

    def append_row(self, row: list) -> bool:
        if not self.config.SPREADSHEET_ID:
            log.info(f"[Sheets SIMULADO] → {row[2]} | {row[4]} | {row[6][:60]}...")
            return True

        sheet = self._get_sheet()
        if not sheet:
            return False

        try:
            # Busca la última fila con dato en columna A para evitar que
            # fórmulas en otras columnas confundan a append_row y sobreescriba.
            col_a = sheet.col_values(1)
            next_row = len(col_a) + 1
            sheet.insert_rows([row], row=next_row, value_input_option="USER_ENTERED")
            log.info(f"Sheets OK (fila {next_row}) → {row[0]} | {row[2]} | {row[3]} | {row[4]}")
            return True
        except Exception as e:
            log.error(f"Error insertando en Sheets: {e}")
            return False