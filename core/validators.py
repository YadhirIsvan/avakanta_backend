import os
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
ALLOWED_DOCUMENT_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
MAX_IMAGE_SIZE_MB = 10
MAX_DOCUMENT_SIZE_MB = 20

# Magic bytes para validar el contenido real del archivo
_MAGIC_SIGNATURES = {
    'image/jpeg': [b'\xff\xd8\xff'],
    'image/png': [b'\x89PNG\r\n\x1a\n'],
    'image/webp': [b'RIFF'],  # RIFF....WEBP
    'application/pdf': [b'%PDF'],
}


def sanitize_filename(filename):
    """
    Elimina componentes de path (../  /) del nombre de archivo para prevenir path traversal.
    """
    return os.path.basename(filename)


def validate_file_type(file, allowed_types):
    """
    Valida que el mime type del archivo esté en la lista de tipos permitidos.
    Verifica tanto el Content-Type del header como los magic bytes del contenido real.
    """
    content_type = getattr(file, 'content_type', None)
    if content_type not in allowed_types:
        raise ValidationError(
            f'Tipo de archivo no permitido: {content_type}. '
            f'Tipos aceptados: {", ".join(allowed_types)}'
        )

    # Validar magic bytes del contenido real del archivo
    file.seek(0)
    header = file.read(16)
    file.seek(0)

    signatures = _MAGIC_SIGNATURES.get(content_type, [])
    if signatures and not any(header.startswith(sig) for sig in signatures):
        raise ValidationError(
            'El contenido del archivo no coincide con el tipo declarado. '
            'El archivo podría estar corrupto o ser de un tipo diferente.'
        )


def validate_file_size(file, max_size_mb):
    """
    Valida que el tamaño del archivo no exceda el límite en MB.
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    if file.size > max_size_bytes:
        raise ValidationError(
            f'El archivo excede el tamaño máximo permitido de {max_size_mb} MB. '
            f'Tamaño recibido: {round(file.size / 1024 / 1024, 2)} MB'
        )
