# Agent CV - Sistema de Matching CV-JD

Sistema automatizado para evaluar coincidencias entre Currículums Vitae (CVs) y Descripciones de Trabajo (JDs) mediante embeddings y LLMs.

## Arquitectura

```
Extracción → Similitud Vectorial → Evaluación LLM → Reportes JSON
(PDF/TXT)    (Embeddings)        (Gemini)        (Resultados)
```

### Módulos

- **processor_cvs/jds.py**: Extracción de información estructurada de CVs (PDF) y JDs (texto)
- **similarity.py**: Cálculo de similitud mediante embeddings de sentence-transformers
- **evaluator.py**: Evaluación cualitativa con LLM de Google (Gemini)
- **main.py**: Coordinación del proceso completo

### Secciones procesadas

**Para CVs:**
- **Perfil**: Resumen profesional del candidato
- **Experiencia**: Historial laboral y proyectos
- **Formación**: Educación y certificaciones
- **Habilidades**: Competencias técnicas y blandas

**Para JDs y comparación:**
- Perfil (CV) ↔ **Descripción** (JD): Visión general del puesto
- Experiencia (CV) ↔ **Responsabilidades** (JD): Funciones del cargo
- Formación (CV) ↔ **Formación** (JD): Requisitos educativos
- Habilidades (CV) ↔ **Habilidades** (JD): Competencias requeridas

## Requisitos e Instalación

- Python 3.8+
- Dependencias: sentence-transformers, dspy, google-generativeai, pydantic

```bash
# Clonar e instalar
git clone https://github.com/tu-usuario/agent-cv.git
cd agent-cv
pip install -r requirements.txt

# Crear estructura de directorios
mkdir -p data/cvs data/jds outputs/extracted outputs/scores outputs/evaluations
```

## Uso

1. **Preparar archivos**:
   - Colocar PDFs de CVs en `data/cvs/`
   - Colocar archivos texto de JDs en `data/jds/`

2. **Ejecutar el sistema**:
   ```bash
   python src/main.py
   ```

3. **Resultados**:
   - `outputs/extracted/`: Documentos estructurados en JSON
   - `outputs/scores/`: Métricas de similitud por sección
   - `outputs/evaluations/`: Evaluaciones cualitativas por LLM

## Estructura del proyecto

```
agent-cv/
├── data/        # Archivos de entrada (cvs/ y jds/)
├── src/         # Código fuente del sistema
└── outputs/     # Resultados generados
```

## Limitaciones actuales (MVP)

Este MVP tiene áreas específicas para mejora futura:
- Soporte actual solo para español
- Extracción de secciones mejorable
- Sistema de clasificación de matches optimizable
- Base para escalabilidad gradual

## Contribuir

Para contribuir, cree una rama para features (`feature/nueva-funcionalidad`), realice sus cambios, y envíe un Pull Request con descripción clara de las modificaciones.
