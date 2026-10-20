import ast
from refactor_tools import source, write

path = 'app/services/nutrition_export.py'
text = source(path)
tree = ast.parse(text)
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'legacy_projection')
write('app/mappers/nutrition_export.py', '"""Legacy review projection; no persistence or export state transitions."""\n\n' + ast.get_source_segment(text, fn) + '\n')
text = '\n'.join(text.splitlines()[:fn.lineno-1])
text = text.replace('from app.services.attention import AttentionService', '''from sqlalchemy.orm import Session

from app.mappers.nutrition_export import legacy_projection as legacy_projection
from app.repositories.attention import AttentionRepository
from app.repositories.patient import PatientRepository
from app.services.clinical_access import ClinicalAccessService''')
text = text.replace('class NutritionExportService(AttentionService):', '''class NutritionExportService:
    """Coordinates review and manual sending in the caller's session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._attentions = AttentionRepository(session)
        self._patients = PatientRepository(session)

    @property
    def _access(self) -> ClinicalAccessService:
        return ClinicalAccessService(self._attentions, self._patients)
''')
text = text.replace('self._ensure_attention_in_scope(entity, actor_id=actor_id, actor_roles=actor_roles)', '''scope = self._access.attention_scope(actor_id=actor_id, actor_roles=actor_roles)
        self._access.ensure_attention(entity, scope, actor_id=actor_id)''')
text = text.replace('self._ensure_actor_is_linked_professional(', 'self._access.linked_professional(')
write(path, text.rstrip()+'\n')
