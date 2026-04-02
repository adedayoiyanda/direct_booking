"""
routers/chat.py  —  Chatbot flow endpoint.

GET /chat/node/{node_id}  →  Returns a single chat node (public, no auth)

Add to main.py:
    from routers import chat
    app.include_router(chat.router)
"""
from fastapi import APIRouter, HTTPException
from database import db   # service-role client — bypasses RLS for reliable reads

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/node/{node_id}", summary="Get a chat flow node (public)")
def get_chat_node(node_id: int):
    """
    Returns the message text and options array for a given node ID.
    The frontend uses this to drive the button-based chatbot flow.
    """
    result = (
        db.table("chat_flow")
        .select("id, message_text, options")
        .eq("id", node_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Chat node {node_id} not found.")
    return result.data