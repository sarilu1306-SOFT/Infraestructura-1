import streamlit as st
import networkx as nx
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(layout="wide", page_title="Laboratorio Optimalidad y Sink Tree")

st.title("Guía de laboratorio: Optimalidad y Sink Tree en Streamlit")
st.caption("Basada en el estudio de Hartinder Singh Johal (2008) | Extensión Multicriterio")

# --- Inicialización de la Red por Defecto ---
# Se guarda una tabla BASE que no se sobrescribe con las ediciones; las ediciones
# del usuario viven dentro del data_editor y se leen de su resultado.
ENLACES_INICIALES = [
    {"Origen": "H", "Destino": "D", "Retardo_ms": 8.0, "Banda_Mbps": 100.0, "Disponible": True},
    {"Origen": "D", "Destino": "A", "Retardo_ms": 9.0, "Banda_Mbps": 100.0, "Disponible": True},
    {"Origen": "A", "Destino": "B", "Retardo_ms": 7.0, "Banda_Mbps": 100.0, "Disponible": True},
    {"Origen": "H", "Destino": "E", "Retardo_ms": 5.0, "Banda_Mbps": 50.0, "Disponible": True},
    {"Origen": "E", "Destino": "J", "Retardo_ms": 10.0, "Banda_Mbps": 50.0, "Disponible": True},
    {"Origen": "J", "Destino": "C", "Retardo_ms": 8.0, "Banda_Mbps": 100.0, "Disponible": True},
    {"Origen": "C", "Destino": "B", "Retardo_ms": 6.0, "Banda_Mbps": 100.0, "Disponible": True},
    {"Origen": "H", "Destino": "O", "Retardo_ms": 7.0, "Banda_Mbps": 50.0, "Disponible": True},
    {"Origen": "O", "Destino": "N", "Retardo_ms": 9.0, "Banda_Mbps": 50.0, "Disponible": True},
    {"Origen": "N", "Destino": "J", "Retardo_ms": 9.0, "Banda_Mbps": 50.0, "Disponible": True},
]
if "enlaces_base" not in st.session_state:
    st.session_state.enlaces_base = pd.DataFrame(ENLACES_INICIALES)

# --- Barra Lateral (Controles) ---
st.sidebar.header("Configuración de Criterios")
funcion_opt = st.sidebar.selectbox(
    "Función Objetivo",
    ["Johal: Mínimo de saltos", "Mínimo Retardo", "Multicriterio Normalizado"]
)

st.sidebar.subheader("Pesos Multicriterio")
w_alpha = st.sidebar.slider("Peso Saltos (α)", 0.0, 1.0, 0.5, 0.05)
w_beta = st.sidebar.slider("Peso Retardo (β)", 0.0, 1.0, 0.35, 0.05)
w_gamma = st.sidebar.slider("Peso Capacidad (γ)", 0.0, 1.0, 0.15, 0.05)

# Normalización de pesos (cada peso dividido entre la suma)
suma_w = w_alpha + w_beta + w_gamma
if suma_w > 0:
    alpha = w_alpha / suma_w
    beta = w_beta / suma_w
    gamma = w_gamma / suma_w
else:
    alpha, beta, gamma = 1 / 3, 1 / 3, 1 / 3

st.sidebar.info(
    f"Pesos normalizados:\n* α (Saltos): {alpha:.3f}\n* β (Retardo): {beta:.3f}\n* γ (Capacidad): {gamma:.3f}"
)

if st.sidebar.button("Restablecer Valores por Defecto"):
    st.session_state.clear()
    st.rerun()

# --- Sección 1: Consola / Edición de Parámetros ---
st.header("1. Consola de Edición de Enlaces")
df_editado = st.data_editor(
    st.session_state.enlaces_base,
    num_rows="fixed",
    key="editor_enlaces",
    disabled=["Origen", "Destino"],
    column_config={
        "Retardo_ms": st.column_config.NumberColumn("Retardo_ms", min_value=0.0),
        "Banda_Mbps": st.column_config.NumberColumn("Banda_Mbps", min_value=0.1),
        "Disponible": st.column_config.CheckboxColumn("Disponible"),
    },
)

# Validación: no se permiten celdas numéricas vacías
if df_editado[["Retardo_ms", "Banda_Mbps"]].isna().any().any():
    st.error("Hay celdas vacías en Retardo_ms o Banda_Mbps. Complétalas para continuar.")
    st.stop()

# --- Referencias globales d_ref y b_ref (máximos positivos de la tabla actual) ---
retardos_pos = df_editado.loc[df_editado["Retardo_ms"] > 0, "Retardo_ms"]
bandas_pos = df_editado.loc[df_editado["Banda_Mbps"] > 0, "Banda_Mbps"]
d_ref = float(retardos_pos.max()) if len(retardos_pos) > 0 else 1.0
b_ref = float(bandas_pos.max()) if len(bandas_pos) > 0 else 1.0

st.metric("Referencias calculadas de la tabla actual", f"d_ref = {d_ref:g} ms | b_ref = {b_ref:g} Mbps")


def costo_multicriterio(retardo, banda):
    """Ecuación del laboratorio: α + β*(d_ij/d_ref) + γ*(b_ref/b_ij)"""
    return alpha + beta * (retardo / d_ref) + gamma * (b_ref / banda)


# --- Procesamiento del Grafo con NetworkX ---
G = nx.Graph()
# Todos los routers existen como nodos, aunque se queden sin enlaces activos
G.add_nodes_from(pd.unique(df_editado[["Origen", "Destino"]].values.ravel()))

df_activos = df_editado[df_editado["Disponible"] == True]  # noqa: E712

for _, row in df_activos.iterrows():
    u, v = row["Origen"], row["Destino"]
    h_cost = 1.0
    d_cost = float(row["Retardo_ms"])
    b_ij = float(row["Banda_Mbps"])
    if b_ij <= 0:
        continue

    c_cost = costo_multicriterio(d_cost, b_ij)

    # Asignar peso según la función objetivo seleccionada
    if funcion_opt == "Johal: Mínimo de saltos":
        peso_final = h_cost
    elif funcion_opt == "Mínimo Retardo":
        peso_final = d_cost
    else:
        peso_final = c_cost

    G.add_edge(u, v, saltos=h_cost, retardo=d_cost, banda=b_ij, peso=peso_final)

# --- Rutas Estáticas de Control (Artículo) ---
rutas_estaticas = {
    "PSRC": ["H", "D", "A", "B"],
    "SSRC": ["H", "E", "J", "C", "B"],
    "TSRC": ["H", "O", "N", "J", "C", "B"],
}

origen, destino = "H", "B"


def metricas_ruta(ruta):
    """Devuelve las métricas de una ruta, o None si algún enlace no está disponible."""
    saltos, retardo, bandas, costo = 0, 0.0, [], 0.0
    for i in range(len(ruta) - 1):
        u, v = ruta[i], ruta[i + 1]
        if not G.has_edge(u, v):
            return None
        e = G[u][v]
        saltos += 1
        retardo += e["retardo"]
        bandas.append(e["banda"])
        costo += costo_multicriterio(e["retardo"], e["banda"])
    return {"saltos": saltos, "retardo": retardo, "banda": min(bandas), "costo": costo}


# --- Sección 2: Visualización y Camino Óptimo ---
st.header("2. Análisis del Camino Óptimo (Origen H ➔ Destino B)")

camino_optimo = []
existe_ruta = G.has_node(origen) and G.has_node(destino) and nx.has_path(G, origen, destino)

if existe_ruta:
    camino_optimo = nx.shortest_path(G, source=origen, target=destino, weight="peso")
    st.success(f"**Camino Óptimo Dinámico Actual:** {' ➔ '.join(camino_optimo)}")
else:
    st.error("¡ERROR! No existe una ruta disponible entre H y B debido a las caídas de enlaces.")

# Análisis comparativo en tabla
metricas_rutas = []
ruta_estatica_sel = None  # primera ruta del artículo que esté disponible
for nombre, ruta in rutas_estaticas.items():
    m = metricas_ruta(ruta)
    if m is not None and ruta_estatica_sel is None:
        ruta_estatica_sel = nombre
    metricas_rutas.append({
        "Ruta del Artículo": nombre,
        "Recorrido": "–".join(ruta),
        "Factible": "Sí" if m else "No (Enlace Caído)",
        "Saltos H(P)": m["saltos"] if m else "—",
        "Retardo D(P) (ms)": round(m["retardo"], 4) if m else "—",
        "Ancho Banda B(P) (Mbps)": m["banda"] if m else "—",
        "Costo Multicriterio C(P)": round(m["costo"], 4) if m else "—",
    })

df_comparativo = pd.DataFrame(metricas_rutas)
st.subheader("Comparativa de las 3 Rutas Estáticas del Artículo")
st.dataframe(df_comparativo)

# Selección estática (primera disponible) frente al recálculo dinámico
if ruta_estatica_sel is not None:
    recorrido_est = rutas_estaticas[ruta_estatica_sel]
    st.info(f"**Ruta estática seleccionada (primera disponible del artículo):** "
            f"{ruta_estatica_sel} → {' ➔ '.join(recorrido_est)}")
    if existe_ruta:
        if camino_optimo == recorrido_est:
            st.write("La ruta estática **coincide** con el camino óptimo recalculado.")
        else:
            st.write("La ruta estática **difiere** del camino óptimo recalculado "
                     "para la función objetivo seleccionada.")
else:
    st.warning("Ninguna de las tres rutas preconfiguradas del artículo está disponible.")

if existe_ruta:
    m_opt = metricas_ruta(camino_optimo)
    st.subheader("Métricas del camino óptimo dinámico")
    st.dataframe(pd.DataFrame([{
        "Recorrido": "–".join(camino_optimo),
        "Saltos H(P)": m_opt["saltos"],
        "Retardo D(P) (ms)": round(m_opt["retardo"], 4),
        "Ancho Banda B(P) (Mbps)": m_opt["banda"],
        "Costo Multicriterio C(P)": round(m_opt["costo"], 4),
    }]))

# --- Sección 3: Sink Tree hacia Destino B ---
st.header("3. Sink Tree hacia el Destino B")

if G.has_node(destino):
    # Dijkstra desde B: en un grafo no dirigido, el camino B -> nodo invertido es nodo -> B
    distancias, caminos_desde_B = nx.single_source_dijkstra(G, destino, weight="peso")

    tabla_sink = []
    sink_edges = []

    for nodo in sorted(G.nodes()):
        if nodo == destino:
            tabla_sink.append({"Router": nodo, "Siguiente Salto hacia B": "Destino Final", "Costo Acumulado": 0.0})
            continue
        if nodo in caminos_desde_B:
            camino = caminos_desde_B[nodo][::-1]  # nodo -> ... -> B
            sig_salto = camino[1]                 # próximo paso hacia B
            costo_acum = distancias[nodo]
            tabla_sink.append({"Router": nodo, "Siguiente Salto hacia B": sig_salto,
                               "Costo Acumulado": round(costo_acum, 4)})
            sink_edges.append((nodo, sig_salto))
        else:
            tabla_sink.append({"Router": nodo, "Siguiente Salto hacia B": "Aislado", "Costo Acumulado": "—"})

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Tabla de Siguientes Saltos")
        st.dataframe(pd.DataFrame(tabla_sink))
    with col2:
        st.subheader("Visualización del Grafo")
        pos = {
            "H": [0, 0.5], "D": [1, 2], "A": [2, 2], "B": [3, 1.5],
            "E": [1, 0.5], "J": [2, 0.5], "C": [2.5, 1],
            "O": [0.5, -1], "N": [1.5, -1],
        }
        # Solo los nodos que existen en el grafo y tienen posición definida
        pos = {k: v for k, v in pos.items() if G.has_node(k)}

        sink_set = {frozenset(e) for e in sink_edges}

        def xy(aristas):
            xs, ys = [], []
            for a, b in aristas:
                xs.extend([pos[a][0], pos[b][0], None])
                ys.extend([pos[a][1], pos[b][1], None])
            return xs, ys

        otras = [e for e in G.edges() if frozenset(e) not in sink_set and e[0] in pos and e[1] in pos]
        caidos = [(r["Origen"], r["Destino"]) for _, r in df_editado.iterrows()
                  if not r["Disponible"] and r["Origen"] in pos and r["Destino"] in pos]

        ox, oy = xy(otras)
        cx, cy = xy(caidos)
        sx, sy = xy([e for e in sink_edges if e[0] in pos and e[1] in pos])

        trazas = [
            go.Scatter(x=ox, y=oy, mode="lines", line=dict(width=1.5, color="#BBBBBB"), hoverinfo="none"),
            go.Scatter(x=cx, y=cy, mode="lines", line=dict(width=1.5, color="#D62728", dash="dash"), hoverinfo="none"),
            go.Scatter(x=sx, y=sy, mode="lines", line=dict(width=3, color="#1F4E79"), hoverinfo="none"),
        ]

        node_x, node_y, node_text, node_color = [], [], [], []
        for node in G.nodes():
            if node not in pos:
                continue
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(node)
            if node == destino:
                node_color.append("red")
            elif node in camino_optimo:
                node_color.append("green")
            else:
                node_color.append("blue")

        trazas.append(go.Scatter(
            x=node_x, y=node_y, mode="markers+text", text=node_text, textposition="top center",
            hovertext=[f"Router {n}" for n in node_text], hoverinfo="text",
            marker=dict(size=20, color=node_color),
        ))

        fig = go.Figure(data=trazas, layout=go.Layout(
            showlegend=False, hovermode="closest", margin=dict(b=0, l=0, r=0, t=0),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        ))
        # Flechas del Sink Tree: de cada router hacia su siguiente salto
        for a, b in sink_edges:
            if a in pos and b in pos:
                fig.add_annotation(
                    x=pos[b][0], y=pos[b][1], ax=pos[a][0], ay=pos[a][1],
                    xref="x", yref="y", axref="x", ayref="y",
                    showarrow=True, arrowhead=3, arrowsize=1.4, arrowwidth=2,
                    arrowcolor="#1F4E79", standoff=12, startstandoff=12,
                )
        st.plotly_chart(fig)
        st.caption("Rojo: destino B | Verde: camino óptimo H–B | Azul: otros routers | "
                   "Flechas azules: Sink Tree (siguiente salto) | Rojo discontinuo: enlaces caídos | "
                   "Gris: enlaces activos fuera del Sink Tree")
else:
    st.warning("El nodo destino B no está disponible.")

# --- Sección 4: Exportación de Evidencias (CSV) ---
st.header("4. Exportación de Resultados y Evidencias")
df_exportar = df_comparativo.copy()
df_exportar["Funcion_Objetivo_Seleccionada"] = funcion_opt
df_exportar["d_ref"] = d_ref
df_exportar["b_ref"] = b_ref
df_exportar["Pesos_a_b_g"] = f"({alpha:.2f}, {beta:.2f}, {gamma:.2f})"
df_exportar["Ruta_Estatica_Seleccionada"] = ruta_estatica_sel if ruta_estatica_sel else "Ninguna"
df_exportar["Camino_Optimo_Dinamico"] = "–".join(camino_optimo) if camino_optimo else "Sin ruta"

csv = df_exportar.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="Descargar CSV de Resultados (Evidencia del Experimento)",
    data=csv,
    file_name="evidencias_experimento_sink_tree.csv",
    mime="text/csv",
)
