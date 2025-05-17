from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Any, Dict, Literal, Optional
import dspy
import os
import logging
import json
import argparse

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración por defecto para Gemini
GEMINI_CONFIG = {
    "provider": "gemini",
    "model": "gemini-2.0-flash",
    "api_key": "key",
    "max_tokens": 300,
    "temperature": 0
}

# Report of the match between the CV and the JD.

class ReportOutput(BaseModel):
    text: str = Field(..., description="Report of the match between the CV and the JD.")

class MatchLevel(str, Enum):
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"
    MUY_BAJO = "muy_bajo"

class ClassificationResult(BaseModel):
    match_level: MatchLevel = Field(..., description="Match level between sections of the CV and the JD.")
    report: ReportOutput = Field(..., description="Report of the match between the CV and the JD.")


#
class Evaluate(dspy.Signature):
    """Evaluate the match between the CV and the JD."""

    cv: str = dspy.InputField(desc="Curriculum Vitae of the candidate.")
    jd: str = dspy.InputField(desc="Job Description of the job.")
    scores: str = dspy.InputField(desc="Similarity scores between CV and JD.")
    result: ClassificationResult = dspy.OutputField(desc="Result of the evaluation.")


def configure_llm(model_name=None, api_key=None, temperature=None, max_tokens=None):
    """Configure the LLM for evaluation."""
    # Usar valores de GEMINI_CONFIG por defecto si no se proporcionan
    provider = GEMINI_CONFIG["provider"]
    model = model_name or GEMINI_CONFIG["model"]
    key = api_key or GEMINI_CONFIG["api_key"]
    temp = temperature if temperature is not None else GEMINI_CONFIG["temperature"]
    tokens = max_tokens or GEMINI_CONFIG["max_tokens"]
    model_name = f"{provider}/{model}"
    
    # Crear y configurar el modelo LLM
    lm = dspy.LM(
        model_name,
        api_key=key,
        temperature=temp,
        max_tokens=tokens
    )
    dspy.settings.configure(lm=lm)
    logger.info(f"LLM configurado: {model}, temperatura: {temp}, tokens: {tokens}")
    return lm


def determine_match_level(score):
    """Determina el nivel de coincidencia basado en el puntaje total."""
    if score >= 0.7:
        return MatchLevel.ALTO
    elif score >= 0.5:
        return MatchLevel.MEDIO
    elif score >= 0.3:
        return MatchLevel.BAJO
    else:
        return MatchLevel.MUY_BAJO


def format_prompt_data(cv_data, jd_data, scores_data):
    """Formatea los datos para enviarlos al LLM."""
    # Extraer las secciones principales
    cv_sections = {
        "perfil": cv_data.get("perfil", ""),
        "experiencia": cv_data.get("experiencia", ""),
        "formacion": cv_data.get("formacion", ""),
        "habilidades": cv_data.get("habilidades", "")
    }
    
    jd_sections = {
        "descripcion": jd_data.get("descripcion", ""),
        "responsabilidades": jd_data.get("responsabilidades", ""),
        "formacion": jd_data.get("formacion", ""),
        "habilidades": jd_data.get("habilidades", "")
    }
    
    # Simplificar para que el contexto no sea demasiado grande
    cv_summary = "\n".join([f"{k.upper()}: {v[:150]}..." for k, v in cv_sections.items() if v])
    jd_summary = "\n".join([f"{k.upper()}: {v[:150]}..." for k, v in jd_sections.items() if v])
    
    # Incluir scores
    section_scores = scores_data.get("scores", {})
    section_scores_text = ""
    for section, score in section_scores.items():
        section_scores_text += f"- {section}: {score*100:.1f}%\n"
    
    total_score = scores_data.get("total_score", 0)
    match_level = determine_match_level(total_score)
    
    # Formato final
    prompt_data = f"""
CV DEL CANDIDATO:
----------------
{cv_summary}

DESCRIPCIÓN DEL TRABAJO:
-----------------------
{jd_summary}

RESULTADOS DE COINCIDENCIA:
-------------------------
Score Total: {total_score*100:.1f}%
Nivel de Coincidencia: {match_level.value.upper()}

Scores por sección:
{section_scores_text}
"""
    return prompt_data, match_level


def evaluate_match(cv_text, jd_text, scores=None):
    """
    Evaluate the match between a CV and a JD.
    
    Args:
        cv_text (str): The CV content as JSON string or dict.
        jd_text (str): The JD content as JSON string or dict.
        scores (dict, optional): Scores data if available.
        
    Returns:
        ClassificationResult: The evaluation result with match level and report.
    """
    try:
        # Preparar evaluador
        evaluator = dspy.ChainOfThought(Evaluate)
        
        # Convertir a diccionarios si son strings JSON
        if isinstance(cv_text, str):
            try:
                cv_data = json.loads(cv_text)
            except:
                logger.warning("CV text no es JSON válido, usando como está")
                cv_data = {"texto_completo": cv_text}
        else:
            cv_data = cv_text
            
        if isinstance(jd_text, str):
            try:
                jd_data = json.loads(jd_text)
            except:
                logger.warning("JD text no es JSON válido, usando como está")
                jd_data = {"texto_completo": jd_text}
        else:
            jd_data = jd_text
        
        # Si hay scores, formatear el prompt
        scores_input = ""
        match_level = MatchLevel.MUY_BAJO
        
        if scores:
            scores_input, match_level = format_prompt_data(cv_data, jd_data, scores)
        
        # Realizar evaluación
        prediction = evaluator(
            cv=json.dumps(cv_data, ensure_ascii=False),
            jd=json.dumps(jd_data, ensure_ascii=False),
            scores=scores_input
        )
        
        # Verificar el resultado
        if hasattr(prediction, 'result') and isinstance(prediction.result, ClassificationResult):
            return prediction.result
        
        # Si el resultado no está en el formato esperado, crear uno
        if hasattr(prediction, 'result'):
            if hasattr(prediction.result, 'match_level') and hasattr(prediction.result, 'report'):
                # Construir manualmente para asegurar el formato correcto
                return ClassificationResult(
                    match_level=prediction.result.match_level,
                    report=ReportOutput(text=prediction.result.report.text)
                )
            elif isinstance(prediction.result, dict):
                # Extraer del diccionario
                return ClassificationResult(
                    match_level=prediction.result.get('match_level', match_level),
                    report=ReportOutput(text=prediction.result.get('report', {}).get('text', 'No report generated.'))
                )
        
        # Fallback: generar resultado basado en scores si disponibles
        return ClassificationResult(
            match_level=match_level,
            report=ReportOutput(text=f"Evaluación automática basada en score: {match_level.value.upper()}")
        )
        
    except Exception as e:
        logger.error(f"Error evaluando match: {e}")
        # Retornar un resultado por defecto en caso de error
        return ClassificationResult(
            match_level=MatchLevel.MUY_BAJO,
            report=ReportOutput(text=f"Error al evaluar: {str(e)}")
        )

def evaluate_from_files(cv_path, jd_path, score_path, output_path=None):
    """
    Evalúa la coincidencia entre un CV y un JD utilizando archivos de entrada.
    
    Args:
        cv_path (str): Ruta al archivo JSON del CV
        jd_path (str): Ruta al archivo JSON del JD
        score_path (str): Ruta al archivo JSON con los resultados de similitud
        output_path (str, optional): Ruta donde guardar el resultado de la evaluación
        
    Returns:
        ClassificationResult: Resultado de la evaluación
    """
    try:
        # Cargar archivos
        with open(cv_path, 'r', encoding='utf-8') as f:
            cv_data = json.load(f)
        
        with open(jd_path, 'r', encoding='utf-8') as f:
            jd_data = json.load(f)
        
        with open(score_path, 'r', encoding='utf-8') as f:
            scores_data = json.load(f)
            
        # Evaluar con los datos cargados
        result = evaluate_match(cv_data, jd_data, scores_data)
        
        # Crear objeto evaluación para guardarlo
        cv_name = os.path.splitext(os.path.basename(cv_path))[0]
        jd_name = os.path.splitext(os.path.basename(jd_path))[0]
        
        evaluation = {
            "cv_name": cv_name,
            "jd_name": jd_name,
            "match_level": result.match_level.value,
            "report": result.report.text,
            "score": scores_data.get("total_score", 0)
        }
        
        # Guardar evaluación si se especificó ruta
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(evaluation, f, ensure_ascii=False, indent=4)
            logger.info(f"Evaluación guardada en: {output_path}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error evaluando desde archivos: {e}")
        # Retornar un resultado por defecto en caso de error
        return ClassificationResult(
            match_level=MatchLevel.MUY_BAJO,
            report=ReportOutput(text=f"Error al evaluar desde archivos: {str(e)}")
        )