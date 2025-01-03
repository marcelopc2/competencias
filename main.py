import streamlit as st
import requests
from decouple import config
import pandas as pd
from collections import defaultdict
import time

# Configuración inicial
st.set_page_config(page_title="Consultador de competencias! 🤖", page_icon="🤖")
st.title("Buscador de Competencias por Curso 🤖".upper())
st.write("Ingresa el id de un curso y presiona el boton para obtener el detalle de las competencias de los estudiantes.")

# Ingresar Token y URL de Canvas
canvas_token = config("TOKEN")
canvas_base_url = 'https://canvas.uautonoma.cl'

# Ingresar el ID del curso
course_id = st.text_input("ID del curso", "")

def get_course_details(course_id, api_url, headers):
    """
    Obtiene los detalles de un curso en Canvas y el nombre de su subcuenta.
    
    Parámetros:
        course_id (int): ID del curso en Canvas.
        api_url (str): URL base de la API de Canvas.
        headers (dict): Encabezados para la autenticación de la API.

    Retorna:
        dict: Un diccionario con el nombre del curso, sis_course_id, course_code y nombre de la subcuenta.
    """
    try:
        # Endpoint del curso
        course_url = f"{api_url}/api/v1/courses/{course_id}"
        course_response = requests.get(course_url, headers=headers)
        course_response.raise_for_status()
        course_data = course_response.json()

        # Extraer el ID de la subcuenta
        account_id = course_data.get("account_id")

        # Endpoint de la subcuenta
        account_url = f"{api_url}/api/v1/accounts/{account_id}"
        account_response = requests.get(account_url, headers=headers)
        account_response.raise_for_status()
        account_data = account_response.json()

        # Construir el resultado
        course_details = {
            "course_name": course_data.get("name"),
            "sis_course_id": course_data.get("sis_course_id"),
            "course_code": course_data.get("course_code"),
            "subaccount_name": account_data.get("name"),
        }

        return course_details

    except requests.exceptions.RequestException as e:
        raise ValueError(f"Error al obtener la información del curso: {e}")


def fetch_all_results(headers, base_url, course_id):
    """Obtiene todos los resultados iterando página por página."""
    resultados = []
    page = 1
    while True:
        url = f"{base_url}/api/v1/courses/{course_id}/outcome_results?per_page=100&page={page}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json().get('outcome_results', [])
            if not data:  # Si no hay más resultados, detenemos el ciclo
                break
            resultados.extend(data)
            page += 1
        else:
            st.error(f"No se pudo obtener los datos en la página {page}. Código de error: {response.status_code}, contacte con el administrador.")
            break
    return resultados

# def style_table(df):
#     """Aplica estilos a la tabla para fijar el ancho de las columnas y colores a los porcentajes."""
#     def color_percentage(val):
#         """Genera un gradiente de color de rojo (0%) a verde (100%)."""
#         porcentaje = float(val.strip('%'))
#         if porcentaje >= 90:
#             return 'background-color: #4CAF50; color: white;'  # Verde
#         elif porcentaje >= 70:
#             return 'background-color: #FFC107; color: black;'  # Amarillo
#         elif porcentaje >= 50:
#             return 'background-color: #FF9800; color: black;'  # Naranja
#         else:
#             return 'background-color: #F44336; color: white;'  # Rojo

#     styles = [
#         {'selector': 'th', 'props': [('text-align', 'left')]},
#         {'selector': 'td', 'props': [('text-align', 'left')]},
#         # {'selector': 'table', 'props': [('width', '100%')]},
#         {'selector': '.col0', 'props': [('width', '60%')]},
#         {'selector': '.col1', 'props': [('width', '35%')]}, 
#         {'selector': '.col2', 'props': [('width', '5%'),('text-align', 'center')]},# Porcentaje
#     ]
#     return df.style.set_table_styles(styles).map(color_percentage, subset=['Porcentaje'])

def style_table(df):
    """Aplica estilos a la tabla para fijar el ancho de las columnas y colores basados en la categoría."""
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
        return ''  # Sin estilo si no coincide

    styles = [
        {'selector': 'th', 'props': [('text-align', 'left')]},
        {'selector': 'td', 'props': [('text-align', 'left')]},
        {'selector': '.col0', 'props': [('width', '60%')]},
        {'selector': '.col1', 'props': [('width', '35%')]},
        {'selector': '.col2', 'props': [('width', '5%'), ('text-align', 'center')]},  # Porcentaje
    ]
    return df.style.set_table_styles(styles).map(color_by_category, subset=['Categoría'])

if st.button("Buscar"):
    with st.spinner("Procesando datos, por favor espere 🦾..."):
        start_time = time.time()  # Iniciar el temporizador

        if not canvas_token or not course_id or not canvas_base_url:
            st.error("Por favor, complete todos los campos.")
        else:
            # Llamada inicial para obtener outcome_results
            headers = {
                "Authorization": f"Bearer {canvas_token}",
            }

            resultados = fetch_all_results(headers, canvas_base_url, course_id)

            if resultados:
                course_info = get_course_details(course_id, canvas_base_url, headers)
                # Mostrar cuántos resultados se obtuvieron
                st.write(f"Se obtuvieron {len(resultados)} resultados.")
                st.subheader(course_info["subaccount_name"])
                st.markdown(f"###### Curso: {course_info['course_name']} ({course_info['course_code']})")
                st.divider()
                # Agrupar resultados por competencia y estudiante
                competencias = defaultdict(lambda: defaultdict(list))

                for result in resultados:
                    user_id = result['links']['user']
                    learning_outcome = result['links']['learning_outcome']
                    percent = result.get('percent', 0)

                    # Agrupar por competencia y estudiante
                    competencias[learning_outcome][user_id].append(percent)

                # Procesar los datos agrupados
                resultados_competencias = []
                categorias_estandar = ["Excede el dominio", "Reúne el dominio", "Cerca del dominio", "Muy por debajo del dominio"]

                for outcome_id, estudiantes in competencias.items():
                    # Calcular promedio por estudiante
                    categorias = defaultdict(int)
                    total_estudiantes = len(estudiantes)

                    for user_id, scores in estudiantes.items():
                        promedio = sum(scores) / len(scores) if scores else 0

                        # Clasificar en categorías
                        if promedio >= 0.90:
                            categoria = "Excede el dominio"
                        elif promedio >= 0.60:
                            categoria = "Reúne el dominio"
                        elif promedio >= 0.40:
                            categoria = "Cerca del dominio"
                        else:
                            categoria = "Muy por debajo del dominio"

                        categorias[categoria] += 1

                    # Calcular porcentajes por categoría
                    porcentajes = {cat: (categorias[cat] / total_estudiantes) * 100 if total_estudiantes > 0 else 0 for cat in categorias_estandar}

                    for categoria, porcentaje in porcentajes.items():
                        resultados_competencias.append({
                            "Competencia": outcome_id,
                            "Categoría": categoria,
                            "Porcentaje": f"{porcentaje:.1f}%"  # Formatear porcentaje con un decimal y signo "%"
                        })

                # Obtener nombres descriptivos para las competencias
                nombres_competencias = {}
                for outcome_id in competencias.keys():
                    outcome_url = f"{canvas_base_url}/api/v1/outcomes/{outcome_id}"
                    outcome_response = requests.get(outcome_url, headers=headers)

                    if outcome_response.status_code == 200:
                        outcome_data = outcome_response.json()
                        nombres_competencias[outcome_id] = outcome_data.get("title", f"Competencia {outcome_id}")
                    else:
                        nombres_competencias[outcome_id] = f"Competencia {outcome_id}"

                # Reemplazar IDs por nombres en los resultados
                for resultado in resultados_competencias:
                    resultado["Competencia"] = nombres_competencias.get(resultado["Competencia"], resultado["Competencia"])

                # Mostrar tablas por competencia
                st.subheader("Porcentajes de Estudiantes por Categoría y Competencia")
                competencias_df = pd.DataFrame(resultados_competencias)

                for competencia, datos in competencias_df.groupby("Competencia"):
                    st.markdown(f"#### {competencia}")
                    datos = datos.reset_index(drop=True)  # Eliminar el índice numérico
                    styled_table = style_table(datos)
                    st.write(styled_table.to_html(), unsafe_allow_html=True)
                    st.divider()
            else:
                st.warning("No se encontraron resultados de competencias.")

        # Finalizar el temporizador y mostrar tiempo
        elapsed_time = time.time() - start_time
        st.write(f"Tiempo en generar la respuesta:{elapsed_time:.2f} segundos")
        st.write("¿Te ahorro tiempo esta app 😉?")
