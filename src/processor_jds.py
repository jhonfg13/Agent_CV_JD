# -*- coding: utf-8 -*-
import re
import json
import os
from pathlib import Path

def read_jd_file(file_path):
    """
    Lee un archivo de descripción de trabajo (JD) con manejo de diferentes codificaciones.
    """
    # Lista de codificaciones a intentar
    encodings = ['utf-8', 'latin-1', 'utf-16', 'utf-16-le', 'utf-16-be', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                text = file.read()
                # Verificar si el texto no contiene solo caracteres extraños
                if len(text.strip()) > 0:
                    return text
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error leyendo archivo {file_path}: {e}")
            return None
    
    # Si todas las codificaciones fallan, intentar leer en modo binario y decodificar manualmente
    try:
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            # Detectar y eliminar BOM si existe
            if raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
                # Es un archivo UTF-16 con BOM
                text = raw_data.decode('utf-16')
                return text
            
            # Probar decodificaciones seguras para datos binarios
            for encoding in ['utf-8-sig', 'utf-16', 'latin-1']:
                try:
                    text = raw_data.decode(encoding)
                    # Verificar que el texto decodificado tenga sentido (no solo caracteres raros)
                    if len(text.strip()) > 0:
                        return text
                except UnicodeDecodeError:
                    continue
            
            # Último recurso, forzar decodificación ignorando errores
            return raw_data.decode('latin-1', errors='ignore')
            
    except Exception as e:
        print(f"Error en último intento de lectura {file_path}: {e}")
        return None

def identify_sections(text):
    """
    Identifica las secciones principales de un JD.
    Devuelve un diccionario con las secciones encontradas.
    """
    # Convertir texto a minúsculas para facilitar la identificación de secciones
    text_lower = text.lower()
    
    # Diccionario para almacenar las posiciones de inicio de cada sección
    section_starts = {}
    
    # Patrones para el inicio de cada sección
    section_patterns = {
        'descripcion': r'(?:sobre el rol|descripción del puesto|acerca del rol|oportunidad laboral|acerca de la posición|descripción|sobre nosotros|buscamos|búsqueda|busqueda|oportunidad)',
        'responsabilidades': r'(?:responsabilidades|funciones|tareas|actividades|lo que harás|objetivos|responsabilidades clave|objetivo)',
        'formacion': r'(?:formación|académica|académicos|educación|estudios|certificación|certificaciones|profesional|perfil|experiencia requerida)',
        'habilidades': r'(?:habilidades|competencias|conocimientos|skills|competencias clave|certificaciones|tecnologías|herramientas|lenguajes|sistemas|stack)'
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
    # Si es None o vacío, devolver vacío
    if not text:
        return ""
        
    # Convertir a minúsculas
    text = text.lower()
    
    # Eliminar caracteres especiales excepto letras, números, espacios y comas
    text = re.sub(r'[^\w\s,áéíóúüñ]', ' ', text)
    
    # Reemplazar múltiples espacios con uno solo
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_description(section_text):
    """
    Extrae la descripción del JD.
    Retorna un texto normalizado.
    """
    if not section_text:
        return ""
        
    # Eliminar el título de la sección
    lines = section_text.split('\n')
    if len(lines) > 1:
        section_text = '\n'.join(lines[1:]).strip()
    
    # Normalizar texto
    normalized = normalize_text(section_text)
    
    # Para la descripción, conservamos todo el contenido como un solo texto
    # pero limitamos a las primeras 200 palabras si es muy largo
    words = normalized.split()
    if len(words) > 200:
        normalized = ' '.join(words[:200])
    
    return normalized

def extract_responsibilities(section_text):
    """
    Extrae las responsabilidades del JD.
    Retorna un texto normalizado separado por comas.
    """
    if not section_text:
        return ""
        
    # Eliminar el título de la sección
    lines = section_text.split('\n')
    if len(lines) > 1:
        section_text = '\n'.join(lines[1:]).strip()
    
    # Normalizar texto
    normalized = normalize_text(section_text)
    
    # Dividir por líneas o puntos para identificar items individuales
    items = []
    for line in normalized.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Si la línea comienza con un punto, guión o asterisco, es un item
        if line.startswith('-') or line.startswith('•') or line.startswith('*'):
            items.append(line.lstrip('- •*').strip())
        # Si contiene verbos en infinitivo al inicio (comunes en responsabilidades)
        elif re.match(r'^(desarrollar|diseñar|implementar|crear|gestionar|administrar|coordinar|mantener|analizar)\b', line):
            items.append(line)
        elif len(items) == 0:  # Si aún no hemos añadido nada, tomar las líneas como items individuales
            items.append(line)
    
    # Si no se encontraron items, usar el texto completo
    if not items:
        return normalized
    
    # Unir con comas
    return ', '.join(items)

def extract_education(section_text):
    """
    Extrae los requisitos académicos/formación del JD.
    Retorna un texto normalizado separado por comas.
    """
    if not section_text:
        return ""
        
    # Eliminar el título de la sección
    lines = section_text.split('\n')
    if len(lines) > 1:
        section_text = '\n'.join(lines[1:]).strip()
    
    # Normalizar texto
    normalized = normalize_text(section_text)
    
    # Palabras clave para identificar requisitos académicos
    education_keywords = [
        'ingeniería', 'licenciatura', 'título', 'grado', 'carrera', 'universitario',
        'técnico', 'profesional', 'maestría', 'máster', 'doctorado', 'postgrado',
        'certificación', 'diplomado'
    ]
    
    # Buscar líneas que contengan palabras clave de educación
    education_items = []
    for line in normalized.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Si la línea contiene alguna palabra clave de educación, agregarla
        if any(keyword in line for keyword in education_keywords):
            education_items.append(line)
    
    # Si no se encontraron items específicos, buscar en el texto completo
    if not education_items:
        # Intentar encontrar frases con palabras clave
        for keyword in education_keywords:
            pattern = re.compile(r'[^.!?]*\b' + keyword + r'\b[^.!?]*[.!?]')
            matches = pattern.findall(normalized)
            education_items.extend(matches)
    
    # Si aún no hay items, tomar las primeras líneas que mencionan formación
    if not education_items and 'formación' in normalized:
        for line in normalized.split('\n'):
            if 'formación' in line or 'experiencia' in line:
                education_items.append(line)
                break
    
    # Si no se encontró nada específico, devolver el texto normalizado
    if not education_items:
        return normalized
    
    # Unir con comas
    return ', '.join(education_items)

def extract_skills(section_text):
    """
    Extrae las habilidades técnicas y competencias del JD.
    Retorna un texto normalizado separado por comas.
    """
    if not section_text:
        return ""
        
    # Eliminar el título de la sección
    lines = section_text.split('\n')
    if len(lines) > 1:
        section_text = '\n'.join(lines[1:]).strip()
    
    # Normalizar texto
    normalized = normalize_text(section_text)
    
    # Lista de habilidades técnicas comunes para identificar
    technical_skills = [
        'java', 'python', 'c++', 'javascript', 'html', 'css', 'sql', 'php',
        'ruby', 'excel', 'word', 'powerpoint', 'linux', 'windows', 'docker',
        'aws', 'azure', 'office', 'sap', 'jira', 'git', 'react', 'angular',
        'vue', 'node.js', 'django', 'flask', 'spring', 'rest', 'api',
        'mongodb', 'mysql', 'postgresql', 'oracle', 'databricks', 'spark',
        'powerbi', 'power bi', 'tableau', 'data warehouse', 'etl', 'power automate',
        'machine learning', 'data lake', 'big data', 'hadoop', 'kubernetes',
        'microservices', 'jenkins', 'devops', 'agile', 'scrum'
    ]
    
    # Dividir por líneas y extraer habilidades
    skills = []
    
    # Primero, buscar líneas que comiencen con viñetas o guiones
    for line in normalized.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Si la línea empieza con viñeta o guión (común en listas de habilidades)
        if line.startswith('-') or line.startswith('•') or line.startswith('*'):
            skill = line.lstrip('- •*').strip()
            if skill:
                skills.append(skill)
    
    # Si no se encontraron items con viñetas, buscar tecnologías específicas
    if not skills:
        for skill in technical_skills:
            if skill in normalized:
                # Buscar el contexto alrededor de la habilidad
                pattern = re.compile(r'[^.!?,]*\b' + skill + r'\b[^.!?,]*')
                matches = pattern.findall(normalized)
                if matches:
                    skills.extend(matches)
                else:
                    skills.append(skill)  # Solo añadir el nombre de la habilidad
    
    # Si aún no hay skills identificadas, tomar las líneas cortas como posibles habilidades
    if not skills:
        for line in normalized.split('\n'):
            line = line.strip()
            if line and len(line.split()) <= 5:  # Líneas cortas podrían ser habilidades
                skills.append(line)
    
    # Si sigue sin haber skills, devolver el texto normalizado
    if not skills:
        return normalized
    
    # Eliminar duplicados y unir con comas
    unique_skills = []
    for skill in skills:
        if skill not in unique_skills:
            unique_skills.append(skill)
    
    return ', '.join(unique_skills)

def process_jd(jd_path, output_dir="outputs/extracted"):
    """
    Procesa un archivo de descripción de trabajo (JD), extrae información estructurada y la guarda en JSON.
    
    Args:
        jd_path: Ruta al archivo JD
        output_dir: Directorio donde se guardarán los archivos JSON
    
    Returns:
        La ruta al archivo JSON generado o None si hubo un error
    """
    # Leer el texto del JD
    print(f"Leyendo archivo {jd_path}...")
    text = read_jd_file(jd_path)
    if not text:
        print(f"No se pudo leer el archivo {jd_path}")
        return None
    
    # Validar texto
    if len(text) < 10:
        print(f"Archivo leído pero texto muy corto: {text}")
        return None
        
    print(f"Texto leído con éxito. Longitud: {len(text)} caracteres")
    
    # Muestra una pequeña parte del texto para diagnóstico
    print(f"Muestra del texto: {text[:100]}...")
    
    # Identificar las secciones del JD
    sections = identify_sections(text)
    
    # Si no se identificaron secciones, usar todo el texto
    if not sections:
        print("No se identificaron secciones, usando todo el texto como descripción")
        sections = {
            'descripcion': text
        }
    else:
        print(f"Secciones identificadas: {', '.join(sections.keys())}")
    
    # Crear la estructura JSON simplificada
    jd_data = {
        "descripcion": extract_description(sections.get('descripcion', '')),
        "responsabilidades": extract_responsibilities(sections.get('responsabilidades', '')),
        "formacion": extract_education(sections.get('formacion', '')),
        "habilidades": extract_skills(sections.get('habilidades', ''))
    }
    
    # Guardar en JSON
    filename = os.path.basename(jd_path)
    output_filename = os.path.splitext(filename)[0] + ".json"
    output_path = os.path.join(output_dir, output_filename)
    
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(jd_data, f, ensure_ascii=False, indent=4)
        print(f"JSON guardado en: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error al guardar JSON: {e}")
        return None
