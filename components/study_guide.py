import streamlit as st


def render_study_guide_panel(guide_markdown: str | None):
    panel = st.container(height=760, border=True)

    with panel:
        st.markdown("## Study Guide")

        if not guide_markdown:
            st.info("Upload slides and generate a study guide to begin.")
            return

        st.markdown(guide_markdown, unsafe_allow_html=True)