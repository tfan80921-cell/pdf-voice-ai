"""
Built-in project templates.
Each template can be instantiated into a full Project + Notebooks + seed documents.
"""
from __future__ import annotations

from typing import Any


_VET_SYSTEM = """Eres un médico veterinario especialista en avicultura con más de 15 años de experiencia en granjas comerciales y lotes experimentales de 100 a 500 aves.

Trabajas con un lote de prueba de aproximadamente 200 aves. Tus respuestas deben ser:
- Prácticas y aplicables el mismo día en granja.
- Basadas solo en los documentos de los cuadernos del proyecto.
- Con dosis, edades, frecuencias y umbrales numéricos cuando el material lo permita.
- Claras sobre qué es protocolo estándar y qué es decisión clínica que requiere inspección in situ.

Priorizas en este orden: bienestar animal → bioseguridad → viabilidad del lote → costos.

Si el contexto no trae un dato (dosis, vacuna, fórmula), dilo explícitamente y no inventes números. Indica qué cuaderno o documento haría falta.
Usa unidades del sistema métrico (°C, ml, g, ppm) y edades en días."""

_VET_OPERATING = """Este proyecto tiene tres cuadernos. Úsalos así:

1) Cuaderno "Vacunación y Bioseguridad"
   - Calendarios de vacunación, vías (ocular, agua, spray, inyección), intervalos, refuerzos.
   - Medidas de bioseguridad del galpón de 200 aves: control de acceso, desinfección, cuarentena, manejo de mortalidad.
   - Ante signos de enfermedad: primero revisa este cuaderno.

2) Cuaderno "Nutrición"
   - Programas de alimentación por fase (iniciador, crecimiento, finalización).
   - Consumo esperado de alimento y agua para ~200 aves.
   - Problemas metabólicos, deficiencias y calidad de agua.

3) Cuaderno "Manejo y Producción"
   - Densidad, temperatura, ventilación, iluminación, pesaje y registros diarios.
   - Metas de peso, conversión y mortalidad aceptable en lote de prueba.
   - Rutina diaria del operario.

Reglas de combinación:
- Solo vacuna/desinfección → Cuaderno 1.
- Solo alimento/agua → Cuaderno 2.
- Ambiente/densidad/luz/registros → Cuaderno 3.
- Pregunta mixta → cruza los cuadernos necesarios; prioriza signos clínicos y bioseguridad.
- Indica siempre de qué cuaderno sale cada recomendación.
- Si faltan datos del lote (edad, genética, bebederos), pídelos antes de dar dosis o densidades definitivas."""

_VET_NB_VACUNA = """LOTE DE PRUEBA ~200 AVES – VACUNACIÓN Y BIOSEGURIDAD
(Referencia operativa; ajustar a etiqueta del laboratorio y línea genética)

1. PREMISAS
- Lote cerrado: no mezclar edades en el mismo galpón.
- Capacidad orientativa: 200 aves ±10%.
- Toda vacuna se aplica según ficha del fabricante; este texto solo orienta calendario y logística.

2. CALENDARIO TÍPICO POLLO DE ENGORDE (días de vida)
- Día 1 (planta o llegada): Marek (si aplica en planta) + control de calidad de pollito.
- Día 7–10: Newcastle + Bronquitis infecciosa (vía ocular o agua, según producto).
- Día 14–18: Gumboro (IBD), según presión de campo y producto.
- Día 21–25: Refuerzo Newcastle (si el programa lo indica).
- No vacunar aves enfermas, deshidratadas o en estrés térmico extremo.

3. LOGÍSTICA PARA 200 AVES
- Preparar vacuna para el número real de aves + 5–10% de merma de aplicación.
- Agua de vacunación: retirar bebederos 1–2 h antes (según clima); usar agua limpia sin desinfectante residual.
- Tiempo de consumo del agua medicada/vacunal: ideal 1–2 horas.
- Registrar: fecha, vacuna, lote del frasco, vía, responsable, reacciones a 24–48 h.

4. BIOSEGURIDAD MÍNIMA (GALPÓN 200)
- Un solo acceso; pedal o bandeja desinfectante a la entrada.
- Ropa/calzado exclusivo del galpón.
- Control de visitas: libro de registro (nombre, fecha, último contacto con aves).
- Mortalidad: retiro al menos 2 veces al día; depósito cerrado lejos del galpón.
- Limpieza en seco diaria; lavado y desinfección total solo entre lotes (all-in/all-out).

5. SEÑALES DE ALARMA (avisar al veterinario de campo)
- Mortalidad >1% en 24 h o >3% acumulada en la primera semana sin causa clara.
- Estornudos generalizados, silbidos, ojos llorosos, heces muy líquidas o con sangre.
- Rechazo de alimento >20% respecto al día anterior.
- Sospecha de fallo vacunal: enfermedad en edades cubiertas por el programa.

6. QUÉ NO HACER
- No mezclar vacunas en el mismo diluyente salvo que el laboratorio lo autorice.
- No usar desinfectante en el agua de vacunación.
- No anticipar ni retrasar más de lo indicado sin criterio técnico documentado.
"""

_VET_NB_NUTRICION = """LOTE DE PRUEBA ~200 AVES – NUTRICIÓN Y AGUA

1. FASES ORIENTATIVAS (POLLO DE ENGORDE)
- Iniciador: día 1 a 14 (o según manual de la línea).
- Crecimiento: día 15 a 28.
- Finalización: día 29 a salida.
Ajustar proteína/energía al manual de la genética; no inventar fórmulas aquí.

2. CONSUMO ORIENTATIVO DE ALIMENTO (TOTAL LOTE ~200)
Valores aproximados de referencia (verificar con báscula):
- Semana 1: ~15–25 g/ave/día → ~3–5 kg/día el lote.
- Semana 2: ~35–50 g/ave/día → ~7–10 kg/día.
- Semana 3: ~70–90 g/ave/día → ~14–18 kg/día.
- Semana 4+: según curva de la línea; registrar diario.

3. AGUA
- Relación agua:alimento orientativa 1,6–2,0 : 1 (sube con el calor).
- Bebederos: altura a nivel del dorso; limpiar diariamente.
- Si se medica por agua: calcular volumen real consumido en 2–4 h, no el volumen teórico del tanque lleno.

4. CONTROL DE CALIDAD
- Alimento: sin humedad excesiva, sin hongos visibles, sin olores a rancio.
- Evitar ayunos prolongados (>3–4 h en pollitos jóvenes) salvo indicación.
- Tras cambio de fase: observar 48 h rechazo, heces y actividad.

5. PROBLEMAS FRECUENTES
- Cama húmeda + heces pastosas: revisar proteína, grasa, sal, calidad de agua e integridad intestinal.
- Baja de consumo brusca: calor, vacunación reciente, enfermedad, agua insuficiente o mala calidad.
- Picos de mortalidad post-cambio de alimento: revisar transición y micotoxinas (enviar muestra si se sospecha).

6. REGISTROS MÍNIMOS
- Kg de alimento ofrecidos y rechazados (si hay).
- Estimación o medición de agua.
- Peso semanal de muestra (20–30 aves) para curva del lote de 200.
"""

_VET_NB_MANEJO = """LOTE DE PRUEBA ~200 AVES – MANEJO Y PRODUCCIÓN

1. DENSIDAD ORIENTATIVA
- Depende de peso final y ventilación.
- Referencia inicial pollitos: orden de 30–40 aves/m² al inicio, reduciendo según crecimiento y normativa local.
- No superar la densidad que impida acceso libre a comedero y bebedero.

2. TEMPERATURA (POLLITO)
- Recepción: ~32–34 °C a nivel de los pollitos (no solo del termómetro de pared).
- Bajar ~2–3 °C por semana hasta ~20–24 °C según edad y pluma.
- Observar comportamiento: apiñados = frío; alejados de la fuente = calor; uniformes y activos = zona de confort.

3. VENTILACIÓN Y CAMA
- Renovación de aire sin corrientes directas sobre las aves.
- Cama seca y friable; remover zonas húmedas.
- En 200 aves el microclima es sensible: un comedero tapado o un bebedero goteando afecta mucho el lote.

4. ILUMINACIÓN
- Primeros días: fotoperiodo generoso para encontrar alimento y agua (según manual de la línea).
- Después: programa de oscuridad para descanso; evitar cambios bruscos.

5. RUTINA DIARIA DEL OPERARIO (CHECKLIST)
- [ ] Mortalidad: conteo, retiro, registro.
- [ ] Agua: flujo, limpieza, temperatura del agua si hace calor.
- [ ] Alimento: disponibilidad, comedero a altura correcta.
- [ ] Comportamiento: actividad, respiración, distribución en el galpón.
- [ ] Cama y fugas.
- [ ] Temperatura y ventilación.
- [ ] Anotar cualquier tratamiento o vacuna del día.

6. METAS DE SEGUIMIENTO (LOTE PRUEBA)
- Mortalidad primera semana: ideal <1%; investigar si >1–2%.
- Uniformidad: pesaje semanal de muestra.
- Conversión alimenticia: kg alimento / kg ganancia (calcular al cierre del lote).
- Toda desviación grande (peso, mortalidad, consumo) se cruza con vacunación reciente y cambios de ambiente.
"""

_LEGAL_SYSTEM = """Eres un consejero jurídico experto. Analizas contratos, leyes y reglamentos con rigor.
Respondes con precisión, citando artículos o cláusulas cuando el contexto lo permite.
Nunca inventas normativa. Si algo no está en los documentos indexados, dilo claramente
y recomienda consultar la fuente oficial o a un abogado colegiado.
Usa un tono profesional, neutro y orientado a la acción."""

_LEGAL_OPERATING = """Tienes cuadernos por área legal. Úsalos así:
- Cuaderno "Contratos": cláusulas, modelos y jurisprudencia contractual.
- Cuaderno "Normativa Laboral": estatuto de los trabajadores, convenios, obligaciones del empleador.
Cita siempre el cuaderno y el documento de origen. Si la pregunta cruza áreas, combina ambos cuadernos."""

_LEGAL_NB_CONTRATOS = """CUADERNO DE CONTRATOS – NOTAS OPERATIVAS

1. Elementos esenciales de un contrato: consentimiento, objeto y causa.
2. Cláusulas críticas a revisar: duración, rescisión, penalidades, confidencialidad, jurisdicción.
3. Ante ambigüedad: interpretar de buena fe y contra el redactor cuando la ley lo permita.
4. Siempre verificar la ley aplicable indicada en el documento indexado; no asumir códigos de otro país.
"""

_LEGAL_NB_LABORAL = """CUADERNO DE NORMATIVA LABORAL – NOTAS OPERATIVAS

1. Revisar jornada, descansos, salarios mínimos y causales de despido según el material indexado.
2. Documentar siempre fechas, notificaciones y acuses de recibo.
3. Ante duda entre convenio y ley, indicar cuál prevalece según el texto disponible.
4. No dar montos de indemnización si no están en el contexto.
"""

_NUTRI_SYSTEM = """Eres un nutricionista deportivo certificado con experiencia en atletas amateurs y semi-profesionales.
Diseñas planes alimentarios basados en evidencia y en los documentos de los cuadernos.
Respondes de forma clara, con cantidades orientativas (g, ml, kcal) cuando el material lo permita.
Nunca prescribes fármacos ni sustituyes atención médica. Si hay patología (diabetes, TCR, etc.), indícalo y recomienda evaluación clínica.
Priorizas: seguridad → adecuación al deporte → adherencia práctica → costo."""

_NUTRI_OPERATING = """Cuadernos disponibles:

1) "Evaluación y Requerimientos"
   - Cálculo orientativo de calorías, macros y timing según deporte y objetivo (fuerza, resistencia, composición corporal).
2) "Planes y Menús"
   - Ejemplos de menús diarios, snacks pre/post entrenamiento, hidratación.
3) "Suplementación y Alertas"
   - Suplementos con evidencia, contraindicaciones generales y señales de alarma nutricional.

Reglas: pregunta de macros/calorías → cuaderno 1; menú concreto → cuaderno 2; creatina/proteína/etc. → cuaderno 3.
Si faltan peso, edad, deporte u objetivo, pídelos antes de dar un plan cerrado.
Cita siempre el cuaderno de origen."""

_NUTRI_NB1 = """EVALUACIÓN Y REQUERIMIENTOS – NOTAS OPERATIVAS

1. Datos mínimos a pedir: edad, sexo, peso, talla, deporte, sesiones/semana, objetivo (rendimiento, hipertrofia, pérdida de grasa).
2. Estimación orientativa de gasto: TMB × factor de actividad (sedentario 1,2 … muy activo 1,7–1,9). Ajustar ±10–20% según objetivo.
3. Proteína orientativa: 1,4–2,0 g/kg/día en deportistas de fuerza; 1,2–1,6 g/kg en resistencia (verificar con material indexado).
4. Carbohidratos: priorizar alrededor del entrenamiento; grasa: no bajar de ~0,8–1,0 g/kg sin supervisión.
5. Hidratación: ~30–40 ml/kg/día como base; más en calor o sesiones largas.
6. Registrar peso semanal y adherencia; no cambios drásticos de kcal de un día para otro.
"""

_NUTRI_NB2 = """PLANES Y MENÚS – NOTAS OPERATIVAS

1. Estructura típica del día: desayuno, comida, cena + 1–2 snacks según horario de entrenamiento.
2. Pre-entreno (1–3 h): carbohidrato + algo de proteína; evitar grasa/fibra excesiva si hay molestias GI.
3. Post-entreno (0–2 h): proteína (20–40 g orientativos) + carbohidrato según duración/intensidad.
4. Ejemplos de snacks: yogur + fruta, batido de leche + plátano, pan + huevo, frutos secos con moderación.
5. Preferir alimentos reales; ultraprocesados solo como excepción de conveniencia.
6. Adaptar a presupuesto y cultura local del usuario cuando el contexto lo permita.
"""

_NUTRI_NB3 = """SUPLEMENTACIÓN Y ALERTAS – NOTAS OPERATIVAS

1. Suplementos con evidencia más sólida en deporte: creatina monohidrato, proteína en polvo si no se cubre con dieta, cafeína aguda pre-competición (dosis y timing según material).
2. No recomendar “quemadores” milagrosos ni productos sin evidencia.
3. Alertas: pérdida de peso muy rápida, amenorrea, fatiga extrema, lesiones por sobreentrenamiento, signos de TCA → derivar a profesional de salud.
4. Revisar interacciones solo si hay documentación en los cuadernos; si no, indicar que no hay dato en el contexto.
5. Hidratación y sueño pesan más que cualquier suplemento.
"""

_MANT_SYSTEM = """Eres un técnico senior de mantenimiento industrial (mecánico/eléctrico) con experiencia en plantas de producción continua.
Respondes con procedimientos seguros, pasos numerados y criterios de parada cuando el material lo indica.
Priorizas: seguridad de personas → integridad del equipo → continuidad de producción.
No inventas pares de apriete, voltajes ni tolerancias: si no están en el contexto, dilo y pide el manual del fabricante.
"""

_MANT_OPERATING = """Cuadernos:

1) "Seguridad y LOTO" – bloqueo/etiquetado, EPP, permisos de trabajo.
2) "Procedimientos mecánicos" – alineación, lubricación, cambio de rodamientos, cintas.
3) "Procedimientos eléctricos" – tableros, motores, fallas comunes, medidas.

Ante una falla: primero seguridad (cuaderno 1), luego diagnóstico según sea mecánica o eléctrica (2 o 3).
Si la pregunta mezcla ambas, combina y deja claro el orden de intervención.
"""

_MANT_NB1 = """SEGURIDAD Y LOTO – NOTAS OPERATIVAS

1. Antes de intervenir: detener energía (eléctrica, neumática, hidráulica), verificar cero energía, aplicar candado y etiqueta (LOTO).
2. EPP mínimo según tarea: casco, gafas, calzado de seguridad, guantes adecuados; arco eléctrico si aplica.
3. Permiso de trabajo en caliente, espacios confinados o altura según procedimiento de planta.
4. Nunca bypassear protecciones ni retiro de guardas sin autorización y reinstalación posterior.
5. Reportar casi-accidentes; no normalizar condiciones inseguras.
"""

_MANT_NB2 = """PROCEDIMIENTOS MECÁNICOS – NOTAS OPERATIVAS

1. Lubricación: tipo, cantidad y frecuencia según ficha del equipo; exceso también daña.
2. Rodamientos: ruido, temperatura y vibración como síntomas; no martillar pistas.
3. Correas/cadenas: tensión correcta, alineación de poleas, desgaste uniforme.
4. Fugas de aceite/aire: localizar, limpiar, reparar; no solo rellenar de forma crónica.
5. Tras intervención: prueba en vacío si es posible, luego carga progresiva y registro en bitácora.
"""

_MANT_NB3 = """PROCEDIMIENTOS ELÉCTRICOS – NOTAS OPERATIVAS

1. Medir solo con instrumento adecuado y categoría de seguridad correcta.
2. Motores: verificar tensión por fase, consumo, temperatura, sentido de giro.
3. Tableros: etiquetado de circuitos, apriete de bornes en paradas programadas, limpieza de polvo.
4. Fallas frecuentes: contactos pegados, térmicos disparados, bornes sueltos, humedad.
5. No abrir equipos bajo tensión salvo procedimiento y calificación explícitos.
"""


TEMPLATES: dict[str, dict[str, Any]] = {
    "vet-avicola-200": {
        "id": "vet-avicola-200",
        "name": "Veterinario Avícola – Lote 200",
        "description": (
            "Proyecto completo para un lote experimental de ~200 aves: "
            "persona veterinaria, reglas de uso de cuadernos y contenido base "
            "de vacunación, nutrición y manejo."
        ),
        "icon": "🐔",
        "category": "agropecuaria",
        "system_instruction": _VET_SYSTEM,
        "operating_instruction": _VET_OPERATING,
        "notebooks": [
            {
                "id": "vacunacion-bioseguridad",
                "name": "Vacunación y Bioseguridad",
                "description": "Protocolos de vacunas, calendarios y bioseguridad",
                "domain": "vacunación aviar, bioseguridad",
                "seed_files": [
                    {"filename": "protocolo_vacunacion_lote_200.txt", "content": _VET_NB_VACUNA},
                ],
            },
            {
                "id": "nutricion",
                "name": "Nutrición",
                "description": "Formulaciones, consumo y agua para ~200 aves",
                "domain": "nutrición aviar",
                "seed_files": [
                    {"filename": "nutricion_lote_200.txt", "content": _VET_NB_NUTRICION},
                ],
            },
            {
                "id": "manejo-produccion",
                "name": "Manejo y Producción",
                "description": "Densidad, ambiente, checklist diario",
                "domain": "manejo productivo avícola",
                "seed_files": [
                    {"filename": "manejo_lote_200.txt", "content": _VET_NB_MANEJO},
                ],
            },
        ],
    },
    "consejero-juridico": {
        "id": "consejero-juridico",
        "name": "Consejero Jurídico",
        "description": "Asesor legal con cuadernos de contratos y normativa laboral.",
        "icon": "⚖️",
        "category": "legal",
        "system_instruction": _LEGAL_SYSTEM,
        "operating_instruction": _LEGAL_OPERATING,
        "notebooks": [
            {
                "id": "contratos",
                "name": "Contratos",
                "description": "Cláusulas y modelos contractuales",
                "domain": "derecho contractual",
                "seed_files": [
                    {"filename": "notas_contratos.txt", "content": _LEGAL_NB_CONTRATOS},
                ],
            },
            {
                "id": "normativa-laboral",
                "name": "Normativa Laboral",
                "description": "Jornada, despidos, convenios",
                "domain": "derecho laboral",
                "seed_files": [
                    {"filename": "notas_laboral.txt", "content": _LEGAL_NB_LABORAL},
                ],
            },
        ],
    },
    "nutricionista-deportivo": {
        "id": "nutricionista-deportivo",
        "name": "Nutricionista Deportivo",
        "description": (
            "Planes alimentarios para deportistas: requerimientos, menús y suplementación "
            "con evidencia, en tres cuadernos operativos."
        ),
        "icon": "🥗",
        "category": "salud",
        "system_instruction": _NUTRI_SYSTEM,
        "operating_instruction": _NUTRI_OPERATING,
        "notebooks": [
            {
                "id": "evaluacion-requerimientos",
                "name": "Evaluación y Requerimientos",
                "description": "Calorías, macros e hidratación según deporte",
                "domain": "nutrición deportiva, requerimientos",
                "seed_files": [
                    {"filename": "evaluacion_requerimientos.txt", "content": _NUTRI_NB1},
                ],
            },
            {
                "id": "planes-menus",
                "name": "Planes y Menús",
                "description": "Menús diarios y timing pre/post entreno",
                "domain": "menús deportivos",
                "seed_files": [
                    {"filename": "planes_menus.txt", "content": _NUTRI_NB2},
                ],
            },
            {
                "id": "suplementacion-alertas",
                "name": "Suplementación y Alertas",
                "description": "Suplementos con evidencia y señales de alarma",
                "domain": "suplementación deportiva",
                "seed_files": [
                    {"filename": "suplementacion_alertas.txt", "content": _NUTRI_NB3},
                ],
            },
        ],
    },
    "mantenimiento-industrial": {
        "id": "mantenimiento-industrial",
        "name": "Técnico de Mantenimiento Industrial",
        "description": (
            "Procedimientos de mantenimiento mecánico y eléctrico con prioridad en seguridad LOTO."
        ),
        "icon": "🔧",
        "category": "industrial",
        "system_instruction": _MANT_SYSTEM,
        "operating_instruction": _MANT_OPERATING,
        "notebooks": [
            {
                "id": "seguridad-loto",
                "name": "Seguridad y LOTO",
                "description": "Bloqueo/etiquetado, EPP y permisos",
                "domain": "seguridad industrial, LOTO",
                "seed_files": [
                    {"filename": "seguridad_loto.txt", "content": _MANT_NB1},
                ],
            },
            {
                "id": "procedimientos-mecanicos",
                "name": "Procedimientos mecánicos",
                "description": "Lubricación, rodamientos, correas",
                "domain": "mantenimiento mecánico",
                "seed_files": [
                    {"filename": "proc_mecanicos.txt", "content": _MANT_NB2},
                ],
            },
            {
                "id": "procedimientos-electricos",
                "name": "Procedimientos eléctricos",
                "description": "Motores, tableros y fallas comunes",
                "domain": "mantenimiento eléctrico",
                "seed_files": [
                    {"filename": "proc_electricos.txt", "content": _MANT_NB3},
                ],
            },
        ],
    },
}


class TemplateCatalog:
    """Read-only catalog of built-in templates."""

    @staticmethod
    def list_summaries() -> list[dict]:
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "description": t["description"],
                "icon": t.get("icon", "📦"),
                "category": t.get("category", "general"),
                "notebook_count": len(t.get("notebooks", [])),
            }
            for t in TEMPLATES.values()
        ]

    @staticmethod
    def get(template_id: str) -> dict | None:
        return TEMPLATES.get(template_id)

    @staticmethod
    def ids() -> list[str]:
        return list(TEMPLATES.keys())
