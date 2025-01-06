import streamlit as st
import requests
from decouple import config
import pandas as pd
from collections import defaultdict
import time

# Configuración inicial de la app
st.set_page_config(page_title="Promediador de Competencias! 🤖", page_icon="🤖")
st.title("Promediador de Competencias por Curso 🤖".upper())
st.write("Ingresa el ID de un curso y presiona el botón para obtener un promedio por competencia del curso, si marcas la casilla podras ver el detalle de cada criterio.")

# Datos de tu Canvas
canvas_token = config("TOKEN")  # O colócalo directamente en una variable (no recomendado en prod)
canvas_base_url = "https://canvas.uautonoma.cl/api/v1"

# Input de texto para el curso
course_id = st.text_input("Ingresa el id del curso", "")

# Checkbox para mostrar/ocultar detalle
show_details = st.checkbox("Mostrar criterios de cada competencia")

def style_table(df):
    """
    Aplica estilos de color según la categoría.
    Puedes ajustarlo a tu gusto.
    """
    def color_by_category(val):
        """Asigna colores según la categoría."""
        if val == "Excede el dominio":
            return 'background-color: #4CAF50; color: white;'  # Verde
        elif val == "Reúne el dominio":
            return 'background-color: #FFC107; color: black;'  # Amarillo
        elif val == "Cerca del dominio":
            return 'background-color: #FF9800; color: black;'  # Naranja
        elif val == "Muy por debajo del dominio":
            return 'background-color: #F44336; color: white;'  # Rojo
        return ''

    styles = [
        {'selector': 'th', 'props': [('text-align', 'left')]},
        {'selector': 'td', 'props': [('text-align', 'left')]},
    ]
    return df.style.set_table_styles(styles).map(color_by_category, subset=['Categoría'])


def fetch_all_results(headers, base_url, course_id):
    """
    Obtiene TODOS los outcome_results de un curso, paginando hasta que no haya más.
    Devuelve una lista con todos los 'outcome_results'.
    """
    resultados = []
    page = 1
    while True:
        url = f"{base_url}/courses/{course_id}/outcome_results?per_page=100&page={page}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json().get('outcome_results', [])
            if not data:
                break
            resultados.extend(data)
            page += 1
        else:
            st.error(f"No se pudo obtener los datos en la página {page}. "
                     f"Código de error: {response.status_code}. Contacta con el administrador")
            break
    return resultados


def get_outcome_groups(course_id, headers):
    """
    Obtiene los grupos de competencias (Outcome Groups) de un curso (nivel raíz).
    Puede devolver una lista o un dict con 'outcome_groups'.
    """
    url = f"{canvas_base_url}/courses/{course_id}/outcome_groups"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_subgroups(course_id, group_id, headers):
    """
    Retorna los subgrupos de un grupo específico.
    """
    url = f"{canvas_base_url}/courses/{course_id}/outcome_groups/{group_id}/subgroups"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def get_outcomes_in_group(course_id, group_id, headers):
    """
    Retorna la lista de 'relaciones' entre un grupo de competencias y sus Outcomes.
    Cada elemento suele tener la forma:
    {
      "outcome": {"id": 123, "title": "..."},
      ...
    }
    """
    url = f"{canvas_base_url}/courses/{course_id}/outcome_groups/{group_id}/outcomes"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()  # Típicamente es una lista con subclave 'outcome'.


def gather_outcomes_with_titles(course_id, group_id, headers):
    """
    Recolecta (en una lista) TODOS los outcomes (competencias) que vivan en
    este grupo y en sus subgrupos, de forma recursiva.
    
    Devuelve pares (outcome_id, outcome_title).
    """
    results = []

    # 1) Obtener 'relaciones' de este grupo con sus outcomes
    data_outcomes = get_outcomes_in_group(course_id, group_id, headers)
    if isinstance(data_outcomes, list):
        for item in data_outcomes:
            outcome_data = item.get("outcome", {})
            oid = outcome_data.get("id")
            otitle = outcome_data.get("title", f"Outcome {oid}")
            if oid:
                results.append((oid, otitle))

    # 2) Obtener subgrupos
    data_subgroups = get_subgroups(course_id, group_id, headers)
    subgroups_list = []
    if isinstance(data_subgroups, list):
        subgroups_list = data_subgroups
    elif isinstance(data_subgroups, dict):
        subgroups_list = data_subgroups.get("outcome_groups", [])

    # 3) Recorrer cada subgrupo y llamar recursivamente
    for sg in subgroups_list:
        sg_id = sg.get("id")
        if sg_id:
            child_outcomes = gather_outcomes_with_titles(course_id, sg_id, headers)
            results.extend(child_outcomes)

    return results


def get_course_details(course_id, headers):
    """
    Obtiene detalles básicos del curso (nombre, sis_course_id, subcuenta).
    No es estrictamente necesario para el cálculo, pero se usa para mostrar info.
    """
    course_url = f"{canvas_base_url}/courses/{course_id}"
    course_resp = requests.get(course_url, headers=headers)
    course_resp.raise_for_status()
    course_data = course_resp.json()

    account_id = course_data.get("account_id", "")
    account_url = f"{canvas_base_url}/accounts/{account_id}"
    account_resp = requests.get(account_url, headers=headers)
    if account_resp.status_code == 200:
        account_data = account_resp.json()
        subaccount_name = account_data.get("name", "")
    else:
        subaccount_name = ""

    return {
        "course_name": course_data.get("name", f"Curso {course_id}"),
        "sis_course_id": course_data.get("sis_course_id"),
        "course_code": course_data.get("course_code"),
        "subaccount_name": subaccount_name
    }


def clasificar_promedio(promedio):
    """
    Devuelve la categoría en base al promedio (0..1).
    Ajusta si tu lógica es diferente (0..100, etc.).
    """
    if promedio >= 0.90:
        return "Excede el dominio"
    elif promedio >= 0.60:
        return "Reúne el dominio"
    elif promedio >= 0.40:
        return "Cerca del dominio"
    else:
        return "Muy por debajo del dominio"


def calcular_distribucion_categorias(user_to_scores):
    """
    Dado un dict user->[lista_de_scores],
    calcular cuántos usuarios hay en cada categoría y su porcentaje.
    Retorna una lista de dicts con "Categoría" y "Porcentaje".
    """
    categorias_count = defaultdict(int)
    total_users = len(user_to_scores)

    for _, scores in user_to_scores.items():
        if scores:
            promedio = sum(scores) / len(scores)
        else:
            promedio = 0.0
        cat = clasificar_promedio(promedio)
        categorias_count[cat] += 1

    data_distribution = []
    for cat in ["Excede el dominio", "Reúne el dominio", "Cerca del dominio", "Muy por debajo del dominio"]:
        if total_users > 0:
            pct = (categorias_count[cat] / total_users) * 100
        else:
            pct = 0.0
        data_distribution.append({
            "Categoría": cat,
            "Porcentaje": f"{pct:.1f}%"
        })
    return data_distribution


# ------------------------------------------------------------------
# LÓGICA PRINCIPAL: Al hacer clic en "Buscar"
# ------------------------------------------------------------------

if st.button("Buscar Competencias"):
    with st.spinner("Procesando datos, por favor espera..."):
        start_time = time.time()

        if not canvas_token or not course_id or not canvas_base_url:
            st.error("Por favor ingresa al menos un id de curso.")
        else:
            # Encabezados para las llamadas a la API
            headers = {
                "Authorization": f"Bearer {canvas_token}",
            }

            # 1) Obtener TODOS los outcome_results del curso
            resultados = fetch_all_results(headers, canvas_base_url, course_id)
            if not resultados:
                st.warning("No hay competencias en este curso!")
                st.stop()

            # 2) Obtener información del curso (para mostrar en la interfaz)
            course_info = get_course_details(course_id, headers)
            st.subheader(course_info["subaccount_name"])
            st.markdown(f"###### Curso: {course_info['course_name']} ({course_info['course_code']})")
            st.divider()

            # 3) Obtener grupos del curso, filtrar los que empiecen con "cd", "cp", "cg"
            all_groups_data = get_outcome_groups(course_id, headers)
            if isinstance(all_groups_data, list):
                groups_list = all_groups_data
            elif isinstance(all_groups_data, dict):
                groups_list = all_groups_data.get("outcome_groups", [])
            else:
                groups_list = []

            # Filtramos grupos cuyo título inicie con "cd", "cp" o "cg" (ignorar mayúsculas).
            grupos_filtrados = []
            for g in groups_list:
                title_lower = g.get("title", "").strip().lower()
                if title_lower.startswith("cd") or title_lower.startswith("cp") or title_lower.startswith("cg"):
                    grupos_filtrados.append(g)

            if not grupos_filtrados:
                st.warning("No se encontraron competencias compatibles en el curso!")
                st.stop()

            # 4) Para cada grupo filtrado, obtendremos los outcomes (id+title).
            grupo_to_outcomes_info = {}  # { group_title: [(out_id, out_title), ...], ... }

            for grp in grupos_filtrados:
                grp_id = grp.get("id")
                grp_title = grp.get("title", "Sin título")
                if not grp_id:
                    continue

                list_outcomes = gather_outcomes_with_titles(course_id, grp_id, headers)
                if list_outcomes:
                    grupo_to_outcomes_info[grp_title] = list_outcomes

            if not grupo_to_outcomes_info:
                st.warning("Las competencias no tienen criterios asociados.")
                st.stop()

            # 5) Procesar los outcome_results para poder calcular promedios
            outcome_to_user_scores = defaultdict(lambda: defaultdict(list))
            for res in resultados:
                user_id = res.get("links", {}).get("user")
                outcome_id_str = res.get("links", {}).get("learning_outcome")
                percent = res.get("percent", 0.0)

                if outcome_id_str and user_id:
                    try:
                        outcome_id = int(outcome_id_str)
                    except ValueError:
                        outcome_id = outcome_id_str  # Caso raro
                    outcome_to_user_scores[outcome_id][user_id].append(percent)

            # 6) Para cada grupo, calculamos su distribución y, si show_details, el detalle de cada competencia
            st.markdown("###### Competencias encontradas:")

            for grupo_title, outcomes_list in grupo_to_outcomes_info.items():
                # 6.1) Construimos user->[perc] para todos los outcomes de este grupo
                user_scores_in_group = defaultdict(list)
                for (oid, _title) in outcomes_list:
                    if oid in outcome_to_user_scores:
                        for user_id, scores_lst in outcome_to_user_scores[oid].items():
                            user_scores_in_group[user_id].extend(scores_lst)

                # 6.2) Generamos la tabla de distribución de categorías para TODO el grupo
                dist_data_grupo = calcular_distribucion_categorias(user_scores_in_group)
                dist_df_grupo = pd.DataFrame(dist_data_grupo)

                st.markdown(f"#### {grupo_title}")
                # Aplicamos estilo a la tabla
                styled_tbl_grupo = style_table(dist_df_grupo)#.assign(**{"Grupo de Competencias": grupo_title})
                st.write(styled_tbl_grupo.to_html(), unsafe_allow_html=True)

                # 6.3) Si el checkbox "show_details" está activado, mostramos detalle de cada competencia
                if show_details:
                    if outcomes_list:
                        st.markdown("#### **:green[Detalle de cada criterio en esta competencia:]**")
                        for (oid, otitle) in outcomes_list:
                            user_scores_competencia = outcome_to_user_scores.get(oid, {})
                            dist_data_competencia = calcular_distribucion_categorias(user_scores_competencia)
                            dist_df_competencia = pd.DataFrame(dist_data_competencia)

                            st.markdown(f"**{otitle}**")#(ID: {oid})
                            styled_tbl_comp = style_table(dist_df_competencia)#.assign(**{"Competencia": otitle})
                            st.write(styled_tbl_comp.to_html(), unsafe_allow_html=True)

                st.divider()

        elapsed_time = time.time() - start_time
        st.write(f"Tiempo en generar la respuesta: {elapsed_time:.2f} segundos")
        st.write("¿Te ahorró tiempo esta app? ¡Espero que sí! 😄")
