from app.services.pnr_service import PNRService


class _FakePNRRepo:
    def __init__(self):
        self.calls = []

    def upsert(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "pnr-id-1", "pnr_number": kwargs.get("pnr_number")}


class _FakeUserPNRRepo:
    def __init__(self):
        self.saved = []

    def get_latest_pnr_for_user(self, user_id: str):
        return {"pnr_number": "8106636505"}

    def exists(self, user_id: str, pnr_id: str) -> bool:
        return False

    def save_user_pnr(self, user_id: str, pnr_id: str):
        self.saved.append((user_id, pnr_id))
        return {"id": "link-id"}


class _FakeRailwayApi:
    def check_pnr_status(self, pnr_number: str):
        return {
            "PNR": pnr_number,
            "status": "successful",
            "train": [{"trainNumber": "12345", "dateOfJourney": "03-05-2026"}],
            "passengers": [{"currentStatus": "CNF-12"}],
        }


def test_pnr_service_rejects_invalid_pnr():
    svc = PNRService(_FakePNRRepo(), _FakeUserPNRRepo(), _FakeRailwayApi())
    out = svc.check_status(user_id="u1", pnr_number="abc")
    assert out["ok"] is False


def test_pnr_service_saves_successful_pnr():
    pnr_repo = _FakePNRRepo()
    user_repo = _FakeUserPNRRepo()
    svc = PNRService(pnr_repo, user_repo, _FakeRailwayApi())
    out = svc.check_status(user_id="u1", pnr_number="8106636505")
    assert out["ok"] is True
    assert len(pnr_repo.calls) == 1
    assert len(user_repo.saved) == 1

