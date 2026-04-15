from pydantic import BaseModel


class GameResponse(BaseModel):
    id: int
    nom: str
    description: str
    min_players: int
    max_players: int
    ticket_cost: int

    class Config:
        from_attributes = True