from app.core.sanitizer import sanitize_symptoms_text

def test_sanitize_symptoms_text_hides_pii():
    # Texto de entrada con datos reales simulados
    texto_original = "El paciente indica que su RUT es 19.876.543-2 y su teléfono +56912345678. Enviar receta a juan.perez@email.com"
    
    # Ejecutamos tu función
    resultado = sanitize_symptoms_text(texto_original)
    
    # Verificamos que los datos sensibles ya no estén en el texto
    assert "19.876.543-2" not in resultado
    assert "+56912345678" not in resultado
    assert "juan.perez@email.com" not in resultado
    
    # Verificamos que se hayan puesto las etiquetas correctas
    assert "[RUT OCULTO]" in resultado
    assert "[TELÉFONO OCULTO]" in resultado
    assert "[EMAIL OCULTO]" in resultado

def test_sanitize_symptoms_text_empty():
    # Verifica que no se caiga si le mandan un texto vacío
    assert sanitize_symptoms_text("") == ""