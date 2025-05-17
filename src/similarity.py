import os
import json
import numpy as np
from functools import lru_cache
from sentence_transformers import SentenceTransformer

# Configuración de modelos y secciones
CONFIG = {
    "models": {
        "short": "all-MiniLM-L6-v2",    # 384 dimensiones, ideal para textos cortos
        "long": "all-mpnet-base-v2"     # 768 dimensiones, mejor para textos largos
    },
    "sections_map": {
        # Cómo se relacionan las secciones entre CV y JD
        "perfil": "descripcion",
        "experiencia": "responsabilidades",
        "formacion": "formacion",
        "habilidades": "habilidades"
    },
    "section_types": {
        # True = texto corto (usar modelo short), False = texto largo (usar modelo long)
        "perfil": True,
        "descripcion": True,
        "experiencia": False,
        "responsabilidades": False,
        "formacion": False,
        "habilidades": True
    },
    "weights": {
        # Pesos para el cálculo del score final
        "perfil_descripcion": 0.15,
        "experiencia_responsabilidades": 0.35,
        "formacion": 0.20,
        "habilidades": 0.30
    }
}

# Cache para modelos (se cargan solo cuando se necesitan)
_MODELS = {}

def get_model(model_type):
    """Obtiene un modelo de embeddings (con carga perezosa)"""
    if model_type not in _MODELS:
        model_name = CONFIG["models"][model_type]
        _MODELS[model_type] = SentenceTransformer(model_name)
    return _MODELS[model_type]

@lru_cache(maxsize=100)
def get_embedding(text, is_short=True):
    """
    Genera embedding para un texto usando el modelo adecuado.
    Con caché para evitar recalcular embeddings para el mismo texto.
    
    Args:
        text (str): Texto para generar embedding
        is_short (bool): Si es True, usa modelo para textos cortos
        
    Returns:
        numpy.ndarray: Vector de embedding
    """
    if not text or len(text.strip()) == 0:
        # Devolver vector de ceros con dimensiones adecuadas
        dim = 384 if is_short else 768
        return np.zeros(dim)
        
    model_type = "short" if is_short else "long"
    model = get_model(model_type)
    return model.encode(text, convert_to_numpy=True)

def cosine_similarity(vec1, vec2):
    """
    Calcula similitud coseno entre dos vectores.
    
    Args:
        vec1, vec2 (numpy.ndarray): Vectores a comparar
        
    Returns:
        float: Similitud coseno [0,1]
    """
    # Evitar división por cero
    if np.all(vec1 == 0) or np.all(vec2 == 0):
        return 0.0
    
    similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    # Normalizamos a [0,1], aunque generalmente ya está en ese rango
    return max(0.0, min(float(similarity), 1.0))

def compare_sections(cv_data, jd_data):
    """
    Compara todas las secciones relevantes entre un CV y un JD.
    
    Args:
        cv_data (dict): Datos del CV
        jd_data (dict): Datos del JD
        
    Returns:
        dict: Scores por sección y total
    """
    scores = {}
    
    # Procesar cada sección del CV con su equivalente en JD
    for cv_section, jd_section in CONFIG["sections_map"].items():
        # Obtener el tipo de sección (corta o larga)
        is_short_section = CONFIG["section_types"].get(cv_section, True)
        
        # Extraer texto de ambos documentos
        cv_text = cv_data.get(cv_section, "")
        jd_text = jd_data.get(jd_section, "")
        
        # Generar embeddings
        cv_embedding = get_embedding(cv_text, is_short_section)
        jd_embedding = get_embedding(jd_text, is_short_section)
        
        # Calcular similitud
        section_key = f"{cv_section}_{jd_section}"
        scores[section_key] = cosine_similarity(cv_embedding, jd_embedding)
    
    # Calcular score total ponderado
    total_score = sum(
        scores[k] * CONFIG["weights"].get(k, 0.25) 
        for k in scores
    )
    
    return {
        "section_scores": scores,
        "total_score": total_score
    }

def compare_cv_to_jds(cv_path, jd_paths, output_dir="outputs/scores"):
    """
    Compara un CV con múltiples JDs y guarda los resultados.
    
    Args:
        cv_path (str): Ruta al archivo JSON del CV
        jd_paths (list): Lista de rutas a archivos JSON de JDs
        output_dir (str): Directorio para guardar resultados
        
    Returns:
        list: Resultados ordenados por score
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Cargar CV
    try:
        with open(cv_path, 'r', encoding='utf-8') as f:
            cv_data = json.load(f)
            cv_name = os.path.splitext(os.path.basename(cv_path))[0]
    except Exception as e:
        print(f"Error al cargar CV {cv_path}: {e}")
        return []
    
    results = []
    
    # Comparar con cada JD
    for jd_path in jd_paths:
        try:
            with open(jd_path, 'r', encoding='utf-8') as f:
                jd_data = json.load(f)
                jd_name = os.path.splitext(os.path.basename(jd_path))[0]
            
            # Comparar secciones
            comparison = compare_sections(cv_data, jd_data)
            
            # Crear resultado completo
            result = {
                "cv_name": cv_name,
                "jd_name": jd_name,
                "scores": comparison["section_scores"],
                "total_score": comparison["total_score"]
            }
            
            # Guardar resultado individual
            output_file = f"{cv_name}_vs_{jd_name}.json"
            output_path = os.path.join(output_dir, output_file)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            
            results.append(result)
            print(f"Comparación: {cv_name} vs {jd_name} - Score: {result['total_score']:.2f}")
            
        except Exception as e:
            print(f"Error al procesar JD {jd_path}: {e}")
    
    # Ordenar resultados por score
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results

def find_best_matches(cv_name, scores_dir="outputs/scores"):
    """
    Encuentra el mejor JD para un CV específico basado en archivos de resultados existentes.
    
    Args:
        cv_name (str): Nombre del CV para el cual buscar coincidencias
        scores_dir (str): Directorio donde se encuentran archivos de comparación
        
    Returns:
        dict: El mejor JD coincidente para el CV especificado
    """
    try:
        # Buscar todos los archivos de comparación para este CV
        results = []
        
        # Leer todos los archivos que comiencen con el nombre del CV
        for filename in os.listdir(scores_dir):
            if filename.startswith(f"{cv_name}_vs_") and filename.endswith(".json"):
                file_path = os.path.join(scores_dir, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                        results.append(result)
                except Exception as e:
                    print(f"Error al leer archivo {file_path}: {e}")
        
        if not results:
            print(f"No se encontraron comparaciones para el CV: {cv_name}")
            return None
            
        # Ordenar por score de mayor a menor
        results.sort(key=lambda x: x["total_score"], reverse=True)
        
        # Retornar el mejor resultado
        return results[0]
    
    except Exception as e:
        print(f"Error al buscar mejores coincidencias: {e}")
        return None