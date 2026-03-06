import streamlit as st


USER_AVATAR = "\U0001F9D1"
AI_AVATAR = "\U0001F916"


def render_chat_panel() -> str | None:
    st.markdown("## AI Tutor")

    chat_scroll = st.container(height=640, border=True)
    with chat_scroll:
        selected_text = st.session_state.get("selected_text", "")
        if selected_text:
            st.info("Selected Section")
            st.code(selected_text)

        for msg in st.session_state.get("chat_history", []):
            avatar = USER_AVATAR if msg["role"] == "user" else AI_AVATAR
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

    return st.chat_input("Ask the tutor anything about your lecture")