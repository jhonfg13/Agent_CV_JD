import os
import glob
import time
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Importar módulos propios
import processor_cvs
import processor_jds
import similarity
import evaluator

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('agent_cv.log')
    ]
)
logger = logging.getLogger(__name__)

def setup_directories():
    """Crea las carpetas necesarias si no existen."""
    dirs = [
        'outputs/extracted',
        'outputs/scores',
        'outputs/evaluations'
    ]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Verificada carpeta: {dir_path}")

def process_documents():
    """Procesa todos los CVs y JDs disponibles.
    
    Args:
        None
        
    Returns:
        cv_jsons: Lista de rutas a los archivos JSON de CV procesados
        jd_jsons: Lista de rutas a los archivos JSON de JD procesados
    """
    # Procesamiento de CVs
    cv_jsons = []
    cv_files = glob.glob('data/cvs/*.pdf')
    
    if not cv_files:
        logger.warning("No se encontraron archivos PDF de CV")
    else:
        logger.info(f"Encontrados {len(cv_files)} CVs para procesar")
    
    for cv_path in cv_files:
        try:
            start_time = time.time()
            json_path = processor_cvs.process_cv_simplified(cv_path)
            if json_path:
                cv_jsons.append(json_path)
                duration = time.time() - start_time
                logger.info(f"CV procesado: {os.path.basename(cv_path)} ({duration:.2f}s)")
            else:
                logger.error(f"Error al procesar CV: {cv_path}")
        except Exception as e:
            logger.error(f"Excepción al procesar CV {cv_path}: {e}")
    
    # Procesamiento de JDs
    jd_jsons = []
    jd_files = glob.glob('data/jds/*.txt')
    
    if not jd_files:
        logger.warning("No se encontraron archivos de JD")
    else:
        logger.info(f"Encontrados {len(jd_files)} JDs para procesar")
    
    for jd_path in jd_files:
        try:
            start_time = time.time()
            json_path = processor_jds.process_jd(jd_path)
            if json_path:
                jd_jsons.append(json_path)
                duration = time.time() - start_time
                logger.info(f"JD procesado: {os.path.basename(jd_path)} ({duration:.2f}s)")
            else:
                logger.error(f"Error al procesar JD: {jd_path}")
        except Exception as e:
            logger.error(f"Excepción al procesar JD {jd_path}: {e}")
    
    return cv_jsons, jd_jsons

def run_comparison(cv_jsons, jd_jsons):
    """Ejecuta la comparación 1:1 entre CVs y JDs procesados."""
    if not cv_jsons or not jd_jsons:
        logger.error("No hay suficientes documentos procesados para comparar")
        return None
    
    logger.info(f"Iniciando comparación: {len(cv_jsons)} CVs vs {len(jd_jsons)} JDs")
    
    # Vamos a organizar las comparaciones por JD para mantener la estructura esperada
    # pero con resultados 1:1
    all_results = {}
    
    try:
        for cv_path in cv_jsons:
            start_time = time.time()
            # Llamar a similarity.compare_cv_to_jds con un solo CV y todos los JDs
            cv_results = similarity.compare_cv_to_jds(cv_path, jd_jsons)
            
            # Organizar por JD (manteniendo solo el mejor CV por JD)
            for result in cv_results:
                jd_name = result['jd_name']
                if jd_name not in all_results:
                    all_results[jd_name] = []
                
                # Añadir este resultado (los resultados ya vienen ordenados por score)
                all_results[jd_name].append(result)
            
            duration = time.time() - start_time
            logger.info(f"Comparación para {os.path.basename(cv_path)} completada en {duration:.2f} segundos")
        
        # Para cada JD, ordenar resultados por score
        for jd_name in all_results:
            all_results[jd_name].sort(key=lambda x: x['total_score'], reverse=True)
            
        logger.info(f"Todas las comparaciones completadas")
        return all_results
    except Exception as e:
        logger.error(f"Error durante la comparación: {e}")
        return None

def evaluate_match(cv_path, jd_path, score_path):
    """
    Evalúa una coincidencia específica entre CV y JD.
    
    Args:
        cv_path: Ruta al archivo JSON del CV
        jd_path: Ruta al archivo JSON del JD
        score_path: Ruta al archivo JSON con los scores
        
    Returns:
        Un diccionario con la evaluación o None si ocurre un error
    """
    # Configurar LLM (usa la configuración por defecto de GEMINI_CONFIG)
    try:
        evaluator.configure_llm()
        logger.info("LLM configurado correctamente")
    except Exception as e:
        logger.error(f"Error al configurar LLM: {e}")
        return None
    
    # Crear nombre de archivo para la evaluación
    cv_name = os.path.splitext(os.path.basename(cv_path))[0]
    jd_name = os.path.splitext(os.path.basename(jd_path))[0]
    output_path = f"outputs/evaluations/{cv_name}_vs_{jd_name}_eval.json"
    
    # Evaluar coincidencia
    try:
        logger.info(f"Evaluando coincidencia: {cv_name} vs {jd_name}")
        result = evaluator.evaluate_from_files(cv_path, jd_path, score_path, output_path)
        
        # Crear diccionario de evaluación para devolver
        evaluation = {
            "cv_name": cv_name,
            "jd_name": jd_name,
            "match_level": result.match_level.value,
            "report": result.report.text
        }
        
        logger.info(f"Evaluación completada y guardada en: {output_path}")
        return evaluation
    
    except Exception as e:
        logger.error(f"Error al evaluar {cv_name} vs {jd_name}: {e}")
        return None

def print_results(best_matches, evaluations=None):
    """Imprime los resultados de las comparaciones 1:1."""
    if not best_matches:
        logger.info("No hay resultados para mostrar")
        return
    
    print("\n" + "="*50)
    print(" RESULTADOS DE COINCIDENCIA CV-JD ")
    print("="*50)
    
    for jd_name, matches in best_matches.items():
        print(f"\nJD: {jd_name}")
        print("-" * (len(jd_name) + 4))
        
        # Si no hay coincidencias
        if not matches:
            print("  No se encontraron coincidencias")
            continue
            
        # Mostrar top matches con porcentajes (ya organizados por score)
        for idx, match in enumerate(matches, 1):
            # Convertir score a porcentaje (0-100%)
            score_percent = match['total_score'] * 100
            
            # Obtener nivel de coincidencia si está disponible
            match_level = "No evaluado"
            if evaluations and jd_name in evaluations:
                for eval_match in evaluations[jd_name]:
                    if eval_match['cv_name'] == match['cv_name']:
                        match_level = eval_match['match_level'].upper()
                        break
            
            print(f"  #{idx} CV: {match['cv_name']}")
            print(f"     Score: {score_percent:.1f}% | Nivel: {match_level}")
            
            # Mostrar scores por sección
            if match.get('scores'):
                print("     Scores por sección:")
                for section, score in match['scores'].items():
                    section_percent = score * 100
                    print(f"     - {section}: {section_percent:.1f}%")
            
            print()  # Línea en blanco entre candidatos

def main():
    """Función principal que ejecuta todo el flujo."""
    logger.info("Iniciando Agent CV")
    
    # Preparar directorios
    setup_directories()
    
    # Procesar documentos
    logger.info("Iniciando procesamiento de documentos")
    cv_jsons, jd_jsons = process_documents()
    
    # Si hay documentos procesados, ejecutar la comparación
    if cv_jsons and jd_jsons:
        logger.info("Iniciando comparación de documentos")
        best_matches = run_comparison(cv_jsons, jd_jsons)
        
        if not best_matches:
            logger.error("No se obtuvieron resultados de la comparación")
            return
        
        # Mostrar resultados sin evaluación LLM primero
        print_results(best_matches)
        
        # Preguntar al usuario si desea evaluar con LLM
        try:
            eval_choice = input("\n¿Desea evaluar las coincidencias con LLM? (s/n): ").strip().lower()
            if eval_choice != 's':
                logger.info("Usuario eligió no evaluar con LLM")
                return
        except:
            logger.info("No se pudo obtener entrada del usuario, continuando sin evaluación LLM")
            return
        
        # Inicializar diccionario para almacenar evaluaciones
        evaluations = {}
        
        # Evaluar solo el mejor match por cada JD
        for jd_name, matches in best_matches.items():
            if not matches:
                continue
                
            # Tomar el primer match (el mejor)
            best_match = matches[0]
            cv_name = best_match['cv_name']
            
            # Rutas a los archivos necesarios
            cv_path = f"outputs/extracted/{cv_name}.json"
            jd_path = f"outputs/extracted/{jd_name}.json"
            score_path = f"outputs/scores/{cv_name}_vs_{jd_name}.json"
            
            # Verificar que existan los archivos
            if not os.path.exists(cv_path) or not os.path.exists(jd_path) or not os.path.exists(score_path):
                logger.warning(f"Faltan archivos para evaluar {cv_name} vs {jd_name}")
                continue
                
            # Evaluar coincidencia
            evaluation = evaluate_match(cv_path, jd_path, score_path)
            
            if evaluation:
                if jd_name not in evaluations:
                    evaluations[jd_name] = []
                evaluations[jd_name].append(evaluation)
        
        # Mostrar resultados con evaluación
        if evaluations:
            print("\n" + "="*50)
            print(" RESULTADOS CON EVALUACIÓN LLM ")
            print("="*50)
            print_results(best_matches, evaluations)
            logger.info("Proceso completado con éxito, incluyendo evaluación LLM")
        else:
            logger.warning("No se realizaron evaluaciones con LLM")
    else:
        logger.error("No hay suficientes documentos procesados para comparar")
    
    logger.info("Finalizado Agent CV")

if __name__ == "__main__":
    main()