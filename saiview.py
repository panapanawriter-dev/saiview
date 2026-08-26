import streamlit as st
from supabase import create_client
import pandas as pd
import pydeck as pdk
from PIL import Image
import io
import uuid

# Supabase 接続
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.title("SAI VIEW")

# --- 入力フォーム ---
with st.form("report_form"):
    name = st.text_input("名前")
    damage_type = st.selectbox("被害種別", ["倒木", "冠水", "停電", "その他"])
    lat = st.number_input("緯度（latitude）", format="%.6f")
    lon = st.number_input("経度（longitude）", format="%.6f")
    comment = st.text_area("コメント")

    uploaded_file = st.file_uploader("現場写真をアップロード", type=["jpg", "jpeg", "png"])

    submitted = st.form_submit_button("送信")

# --- Supabase に保存 ---
if submitted:
    photo_url = None

    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        img.thumbnail((800, 800))  # 軽量化
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=70)
        buffer.seek(0)

        file_name = f"{uuid.uuid4()}.jpg"
        # ✅ Content-Type を明示
        supabase.storage.from_("reports").upload(
            file_name,
            buffer.read(),
            {"content-type": "image/jpeg"}
        )
        photo_url = supabase.storage.from_("reports").get_public_url(file_name)

    data = {
        "name": name,
        "damage_type": damage_type,
        "lat": lat,
        "lon": lon,
        "comment": comment,
        "photo_url": photo_url
    }

    supabase.table("reports").insert(data).execute()
    st.success("送信しました！")

# --- 地図表示 ---
st.header("災害報告マップ")

res = supabase.table("reports").select("*").execute()
df = pd.DataFrame(res.data)
df = df.dropna(subset=["lat", "lon"])

# 災害種別ごとに色分け
color_map = {
    "倒木": [0, 128, 0],
    "冠水": [0, 0, 255],
    "停電": [255, 255, 0],
    "その他": [255, 0, 0],
}
df["color"] = df["damage_type"].apply(lambda x: color_map.get(x, [255, 0, 0]))

# --- 吹き出しHTMLをPython側で生成 ---
def make_tooltip(row):
    html = f"<b>{row['damage_type']}</b><br>{row['comment']}<br>"

    photo_url = row.get("photo_url")

    # --- ここが重要（NaN対策） ---
    if isinstance(photo_url, str) and photo_url.startswith("http"):
        html += f"<img src='{photo_url}' width='150' style='border-radius:8px'><br>"

    html += f"<i>報告者: {row['name']}</i>"
    return html


df["tooltip_html"] = df.apply(make_tooltip, axis=1)

# --- ピンレイヤー ---
layer = pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position='[lon, lat]',
    get_fill_color='color',
    get_radius='zoom * 8',
    radius_min_pixels=4,
    radius_max_pixels=50,
    pickable=True,
)

tooltip = {
    "html": "{tooltip_html}",
    "style": {"backgroundColor": "white", "color": "black"}
}

view_state = pdk.ViewState(
    latitude=33.5902,
    longitude=130.4017,
    zoom=12,
    min_zoom=10,
    max_zoom=18
)

st.pydeck_chart(pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip=tooltip,
    map_style="light"
))
