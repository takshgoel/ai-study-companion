import streamlit as st


def render_sidebar_panel() -> dict:
    event = {
        "uploaded_files": [],
        "remove_file_id": None,
        "generate_clicked": False,
        "additional_context": "",
    }

    panel = st.container(height=760, border=True)

    with panel:
        st.markdown("### Upload Lecture Slides")
        st.caption("Drag and drop PDF or PPTX files")

        event["uploaded_files"] = st.file_uploader(
            "",
            type=["pdf", "pptx"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            key="lecture_uploader",
        )

        event["generate_clicked"] = st.button("Generate Study Guide", use_container_width=True)

        st.markdown("### Uploaded Files")

        docs = st.session_state.get("docs", {})
        if not docs:
            st.info("No files uploaded yet.")
        else:
            for doc_id, doc in docs.items():
                row = st.columns([4, 2])
                row[0].markdown(f":page_facing_up: **{doc['name']}**  \n`{doc['size_human']}`")
                if row[1].button("Remove", key=f"remove_{doc_id}", type="primary", use_container_width=True):
                    event["remove_file_id"] = doc_id

        event["additional_context"] = st.text_area(
            "Additional Context",
            placeholder="Optional instructor notes, exam focus, or chapter priorities.",
            key="additional_context",
        )

    return event