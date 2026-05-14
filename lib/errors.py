"""Excepciones tipadas de El Despacho."""


class DespachoError(Exception):
    """Raíz de toda excepción del dominio."""


class BovedaError(DespachoError):
    """Fallas de cifrado/descifrado o configuración de La Bóveda."""


class CredencialFaltante(DespachoError):
    """Una credencial requerida no está configurada en Los Ajustes."""

    def __init__(self, slot: str):
        self.slot = slot
        super().__init__(f"Credencial '{slot}' no configurada en Los Ajustes")


class PermisoDenegado(DespachoError):
    """El rol del usuario no permite la acción solicitada."""


class RateLimitExcedido(DespachoError):
    """Demasiados intentos en la ventana de tiempo."""


class PortavozError(DespachoError):
    """Fallo emitiendo un evento al Portavoz."""
