import re

def sanitize_symptoms_text(text: str) -> str:
    """
    Detecta y enmascara RUTs, correos y números de teléfono en un texto libre.
    """
    if not text:
        return ""

    # Patrón para RUT chileno (ej: 12.345.678-9, 12345678-9, 12345678-k)
    rut_pattern = r'\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b'
    
    # Patrón para correo electrónico
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Patrón para celular chileno (ej: +56912345678, 912345678, +56 9 1234 5678)
    phone_pattern = r'(?:\+?56\s?)?9\s?\d{4}\s?\d{4}\b'

    # Reemplazos
    sanitized_text = re.sub(rut_pattern, '[RUT OCULTO]', text)
    sanitized_text = re.sub(email_pattern, '[EMAIL OCULTO]', sanitized_text)
    sanitized_text = re.sub(phone_pattern, '[TELÉFONO OCULTO]', sanitized_text)

    return sanitized_text

# --- Pequeña prueba local (puedes borrar esto después) ---
if __name__ == "__main__":
    texto_prueba = "El paciente indica que su RUT es 19.876.543-2 y su teléfono +56912345678. Enviar receta a juan.perez@email.com por favor."
    print("Texto original:", texto_prueba)
    print("Texto sanitizado:", sanitize_symptoms_text(texto_prueba))