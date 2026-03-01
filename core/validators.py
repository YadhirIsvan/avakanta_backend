from django.core.exceptions import ValidationError

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
ALLOWED_DOCUMENT_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
MAX_IMAGE_SIZE_MB = 10
MAX_DOCUMENT_SIZE_MB = 20


def validate_file_type(file, allowed_types):
    """
    Valida que el mime type del archivo esté en la lista de tipos permitidos.
    """
    content_type = getattr(file, 'content_type', None)
    if content_type not in allowed_types:
        raise ValidationError(
            f'Tipo de archivo no permitido: {content_type}. '
            f'Tipos aceptados: {", ".join(allowed_types)}'
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
