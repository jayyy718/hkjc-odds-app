import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io

st.title("Test Chart Page")

if st.button("🧪 顯示測試圖表"):
    fig, ax = plt.subplots()
    ax.bar([1, 2, 3], [10, 5, 8])
    ax.set_title("Simple Test Chart")

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    st.image(buf, caption="If you see this, chart is OK.")
