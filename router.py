"""
router.py — Determina a qué grupos WhatsApp va cada alerta,
usando el cliente detectado por Claude como pivote.
"""

import logging
from config import Config

log = logging.getLogger(__name__)


class RegionRouter:
    def __init__(self, config: Config):
        self.config = config

    def get_whatsapp_groups(self, cliente: str) -> list[str]:
        """
        Dado el nombre del cliente (tal como aparece en el Form),
        retorna los grupos de WhatsApp que deben recibir la alerta.
        """
        if not cliente:
            return []

        group = self.config.CLIENTE_TO_WHATSAPP_GROUP.get(cliente)
        if group:
            return [group]

        # Fallback: buscar por coincidencia parcial
        for key, grp in self.config.CLIENTE_TO_WHATSAPP_GROUP.items():
            if key.lower() in cliente.lower() or cliente.lower() in key.lower():
                return [grp]

        log.warning(f"Cliente '{cliente}' no tiene grupo WhatsApp mapeado.")
        return []