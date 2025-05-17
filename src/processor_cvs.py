# -*- coding: utf-8 -*-
import fitz  # PyMuPDF
import re
import json
import os
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """Extrae texto de un archivo PDF."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"Error procesando PDF {pdf_path}: {e}")
        return None

def identify_sections(text):
    """
    Identifica las secciones ordenadas por su aparición en el documento.
    """
    # Convertir todo a minúsculas para la búsqueda
    text_lower = text.lower()
    
    # Diccionario para almacenar las posiciones de inicio de cada sección
    section_starts = {}
    
    # Patrones para el inicio de cada sección
    section_patterns = {
        'perfil': r'(?:datos\s+personales|información\s+personal|perfil|sobre\s+mi|acerca\s+de\s+mi|experiencia|habilidad|competencia|capacidad|aptitud|conocimiento)',
        'formacion': r'(?:educación|formación|estudios|certificaciones|cursos)',
        'experiencia': r'(?:experiencia|experiencia\s+laboral|experiencia\s+profesional)',
        'habilidades': r'(?:habilidades|competencias|capacidades|aptitudes|conocimientos|skills|stack|tecnologías)'
    }
    
    # Encontrar dónde comienza cada sección
    for section_name, pattern in section_patterns.items():
        matches = re.search(pattern, text_lower)
        if matches:
            section_starts[section_name] = matches.start()
    
    # Si no se encontraron secciones, devolver diccionario vacío
    if not section_starts:
        return {}
    
    # Ordenar secciones por su posición en el documento
    sorted_sections = sorted(section_starts.items(), key=lambda x: x[1])
    
    # Crear diccionario con el contenido de cada sección
    sections = {}
    
    # Para cada sección, extraer su contenido
    for i, (section_name, start_pos) in enumerate(sorted_sections):
        # Si es la última sección, su contenido va hasta el final
        if i == len(sorted_sections) - 1:
            section_content = text[start_pos:]
        else:
            # Si no es la última, su contenido va hasta donde empieza la siguiente
            next_section_start = sorted_sections[i + 1][1]
            section_content = text[start_pos:next_section_start]
        
        sections[section_name] = section_content.strip()
    
    return sections

def normalize_text(text):
    """
    Normaliza el texto:
    - Convierte a minúsculas
    - Elimina signos especiales
    - Elimina espacios extra
    """
    # Convertir a minúsculas
    text = text.lower()
    
    # Eliminar caracteres especiales excepto letras, números, espacios y comas
    text = re.sub(r'[^\w\s,áéíóúüñ]', ' ', text)
    
    # Reemplazar múltiples espacios con uno solo
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_profile(section_text):
    """
    Extrae información relevante del perfil.
    Retorna un texto normalizado.
    """
    # Limpiar y normalizar
    normalized = normalize_text(section_text)
    
    # Para el perfil, conservamos todo el contenido como un solo texto
    # pero limitamos a las primeras 200 palabras si es muy largo
    words = normalized.split()
    if len(words) > 200:
        normalized = ' '.join(words[:200])
    
    return normalized

def extract_education(section_text):
    """
    Extrae información de educación y formación.
    Retorna un texto normalizado separado por comas.
    """
    # Normalizar texto
    normalized = normalize_text(section_text)
    
    # Buscar títulos académicos comunes
    education_keywords = [
        'licenciatura', 'licenciado', 'ingeniero', 'ingeniería', 'técnico', 
        'máster', 'master', 'doctorado', 'phd', 'grado', 'bachiller', 'profesional', 'maestría',
        'diplomado', 'curso', 'certificación', 'certificado', 'formación', 'especialización', 'postgrado',
    ]
    
    # Dividir por líneas
    lines = normalized.split('\n')
    education_items = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Si la línea contiene alguna palabra clave de educación, agregarla
        if any(keyword in line for keyword in education_keywords):
            education_items.append(line)
        # O si contiene años (posible indicador de periodo educativo)
        elif re.search(r'\b(19|20)\d{2}\b', line):
            education_items.append(line)
    
    # Si no se encontraron elementos con keywords, usar los primeros 5 items no vacíos
    if not education_items:
        education_items = [line for line in lines if line.strip()][:5]
    
    # Unir con comas
    return ', '.join(education_items)

def extract_experience(section_text):
    """
    Extrae información de experiencia laboral.
    Retorna un texto normalizado separado por comas.
    """
    # Normalizar texto
    normalized = normalize_text(section_text)
    
    # Buscar posiciones laborales comunes
    position_keywords = [
        'director', 'gerente', 'jefe', 'coordinador', 'supervisor', 'analista',
        'desarrollador', 'ingeniero', 'técnico', 'asistente', 'consultor',
        'encargado', 'responsable'
    ]
    
    # Dividir por líneas
    lines = normalized.split('\n')
    experience_items = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Si la línea contiene alguna palabra clave de posición, agregarla
        if any(keyword in line for keyword in position_keywords):
            experience_items.append(line)
        # O si contiene años (posible indicador de periodo laboral)
        elif re.search(r'\b(19|20)\d{2}\b', line):
            experience_items.append(line)
    
    # Si no se encontraron elementos con keywords, usar los primeros 5 items no vacíos
    if not experience_items:
        experience_items = [line for line in lines if line.strip()][:5]
    
    # Unir con comas
    return ', '.join(experience_items)

def extract_skills(section_text):
    """
    Extrae habilidades del texto.
    Retorna un texto normalizado separado por comas.
    """
    # Normalizar texto
    normalized = normalize_text(section_text)
    
    # Lista de habilidades técnicas comunes para identificar
    technical_skills = [
        'java', 'python', 'c++', 'javascript', 'html', 'css', 'sql', 'php',
        'ruby', 'excel', 'word', 'powerpoint', 'linux', 'windows', 'docker',
        'aws', 'azure', 'office', 'sap', 'jira', 'git', 'react', 'angular',
        'vue', 'node.js', 'django', 'flask', 'spring', 'rest', 'api',
        'mongodb', 'mysql', 'postgresql', 'oracle'
    ]
    
    # Dividir por líneas y extraer habilidades
    lines = normalized.split('\n')
    skills = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Si la línea empieza con viñeta o guión (común en listas de habilidades)
        if line.startswith('-') or line.startswith('•'):
            skill = line.lstrip('- •').strip()
            if skill:
                skills.append(skill)
        # Si la línea contiene alguna habilidad técnica conocida
        elif any(skill in line for skill in technical_skills):
            skills.append(line)
        # O si es una línea corta (posible skill individual)
        elif len(line.split()) <= 5:
            skills.append(line)
    
    # Si no se encontraron habilidades, usar las keywords técnicas que aparezcan en el texto
    if not skills:
        for skill in technical_skills:
            if skill in normalized:
                skills.append(skill)
    
    # Unir con comas
    return ', '.join(skills)

def process_cv_simplified(pdf_path, output_dir="outputs/extracted"):
    """
    Procesa un CV en PDF, extrae información simplificada y la guarda en JSON.
    
    Args:
        pdf_path: Ruta al archivo PDF del CV
        output_dir: Directorio donde se guardarán los archivos JSON
    
    Returns:
        La ruta al archivo JSON generado o None si hubo un error
    """
    # Extraer el texto completo del PDF
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return None
    
    # Identificar las secciones del CV
    sections = identify_sections(text)
    
    # Crear la estructura JSON simplificada
    cv_data = {
        "perfil": extract_profile(sections.get('perfil', '')),
        "experiencia": extract_experience(sections.get('experiencia', '')),
        "formacion": extract_education(sections.get('formacion', '')),
        "habilidades": extract_skills(sections.get('habilidades', ''))
    }
    
    # Guardar en JSON
    filename = os.path.basename(pdf_path)
    output_filename = os.path.splitext(filename)[0] + ".json"
    output_path = os.path.join(output_dir, output_filename)
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cv_data, f, ensure_ascii=False, indent=4)
        print(f"JSON guardado en: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error al guardar JSON: {e}")
        return None