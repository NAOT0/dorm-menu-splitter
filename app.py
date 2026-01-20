import io
import zipfile
from datetime import datetime, timedelta

import fitz
import streamlit as st
from PIL import Image, ImageDraw

# --- 設定（定数） ---
# A4横向き(150dpi)を基準とした初期座標
DEFAULT_X0, DEFAULT_Y0 = 108, 145
DEFAULT_X1, DEFAULT_Y1 = 1685, 1170
DEFAULT_DPI = 150


@st.cache_data
def get_page_image(file_bytes: bytes, page_idx: int, dpi: int) -> Image.Image:
    """PDFの特定ページを画像化してキャッシュする [cite: 1, 5]。"""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def main():
    hide_style = """
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stAppDeployButton {display: none;}
        </style>
    """
    st.markdown(hide_style, unsafe_allow_html=True)
    """メインアプリのロジック。"""
    st.set_page_config(page_title="献立一括分割ツール", layout="wide")
    st.title("🍴 献立PDF一括分割ツール")
    st.caption("カレンダーの曜日位置に基づき、日付を自動計算して一括保存します")

    uploaded_file = st.file_uploader("献立PDFをアップロードしてください", type="pdf")
    if not uploaded_file:
        st.info("PDFファイルをアップロードして開始してください")
        return

    file_bytes = uploaded_file.getvalue()
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        page_count = doc.page_count

    # --- サイドバー設定 ---
    st.sidebar.header("📅 日付・期間設定")
    target_month = st.sidebar.number_input(
        "処理対象の月", min_value=1, max_value=12, value=datetime.now().month
    )
    first_monday = st.sidebar.date_input(
        "最初のページの「月曜日」にあたる日付", value=datetime(2026, 1, 1)
    )

    st.sidebar.header("📏 範囲設定")
    x0 = st.sidebar.number_input("左端 (x0)", value=DEFAULT_X0)
    y0 = st.sidebar.number_input("上端 (y0)", value=DEFAULT_Y0)
    x1 = st.sidebar.number_input("右端 (x1)", value=DEFAULT_X1)
    y1 = st.sidebar.number_input("下端 (y1)", value=DEFAULT_Y1)
    dpi = st.sidebar.slider("解像度 (DPI)", 72, 300, DEFAULT_DPI)

    # --- プレビュー ---
    st.subheader("1. 範囲と日付の確認")
    template_page = st.selectbox(
        "確認用ページ", range(1, page_count + 1), index=0
    ) - 1
    
    full_img = get_page_image(file_bytes, template_page, dpi)
    page_monday = first_monday + timedelta(days=template_page * 7)

    col_preview, col_crop = st.columns([2, 1])
    with col_preview:
        preview_img = full_img.copy()
        draw = ImageDraw.Draw(preview_img)
        draw.rectangle([x0, y0, x1, y1], outline="red", width=5)
        
        w_step = (x1 - x0) / 7
        for i in range(7):
            lx = x0 + i * w_step
            c_date = page_monday + timedelta(days=i)
            color = "blue" if c_date.month == target_month else "gray"
            draw.line([(lx, y0), (lx, y1)], fill=color, width=2)
            draw.text((lx + 5, y0 + 5),
                      f"{c_date.month}/{c_date.day}", fill=color)
        
        st.image(preview_img, caption=f"ページ {template_page+1}: 範囲確認")

    with col_crop:
        st.write("🔍 切り抜き後イメージ")
        st.image(full_img.crop((x0, y0, x1, y1)), use_column_width=True)

    # --- 実行 ---
    st.divider()
    btn_label = f"🚀 {target_month}月の献立を一括分割して保存"
    if st.button(btn_label):
        zip_buf = io.BytesIO()
        saved_count = 0
        
        with zipfile.ZipFile(zip_buf, "a", zipfile.ZIP_DEFLATED) as zip_f:
            progress = st.progress(0.0)
            for p_idx in range(page_count):
                p_img = get_page_image(file_bytes, p_idx, dpi)
                p_monday = first_monday + timedelta(days=p_idx * 7)
                
                w_step = (x1 - x0) / 7
                for i in range(7):
                    curr_date = p_monday + timedelta(days=i)
                    if curr_date.month != target_month:
                        continue
                    
                    d_left = x0 + i * w_step
                    d_right = d_left + w_step if i < 6 else x1
                    cropped = p_img.crop((d_left, y0, d_right, y1))
                    
                    img_io = io.BytesIO()
                    cropped.save(img_io, format='PNG')
                    # ファイル名は「日付.png」として保存 [cite: 3]
                    zip_f.writestr(f"{curr_date.day}.png", img_io.getvalue())
                    saved_count += 1
                progress.progress((p_idx + 1) / page_count)

        if saved_count > 0:
            st.success(f"{target_month}月の画像を {saved_count} 枚作成しました。")
            st.download_button(
                "📦 ZIPをダウンロード",
                zip_buf.getvalue(),
                f"menu_{target_month:02d}.zip"
            )
        else:
            st.warning("対象月の画像が見つかりません。日付設定を確認してください。")

    # --- 作成者クレジット（フッターに「うっすら」追加） ---
    st.markdown("---")
    st.markdown(
        '<div style="text-align: right; color: gray; font-size: 0.8em; opacity: 0.5;">'
        'Created by カガワナオト'
        '</div>',
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()