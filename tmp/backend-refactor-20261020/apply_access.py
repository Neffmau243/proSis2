from refactor_tools import method, replace_method, source, write
import ast

def delegate(path, cls, name, body):
    original = method(path, cls, name)
    node = next(n for n in ast.parse(source(path)).body if isinstance(n,ast.ClassDef) and n.name==cls)
    fn = next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name==name)
    header = original.splitlines()[:fn.body[0].lineno-min([fn.lineno]+[d.lineno for d in fn.decorator_list])]
    replace_method(path,cls,name,'\n'.join(header)+'\n'+''.join('        '+line+'\n' for line in body.splitlines()))

for module, cls, repo in [('attention','AttentionService','self._attentions, self._patients'),('patient','PatientService','self._repository'),('document','DocumentService','self._documents')]:
    path=f'app/services/{module}.py'
    s=source(path).replace('from app.exceptions import ', 'from app.services.clinical_access import ClinicalAccessService\nfrom app.exceptions import ',1)
    s+='''\n    @property
    def _access(self) -> ClinicalAccessService:
        return ClinicalAccessService('''+repo+''')
'''
    write(path,s)

p='app/services/attention.py'; cls='AttentionService'
delegate(p,cls,'_ensure_actor_is_linked_professional','return self._access.linked_professional(actor_id=actor_id, actor_roles=actor_roles)')
delegate(p,cls,'_ensure_actor_can_cancel_attention','self._access.ensure_cancellation(\n    actor_id=actor_id, actor_roles=actor_roles, professional_id=professional_id,\n    recorded_by_id=recorded_by_id,\n)')
delegate(p,cls,'_ensure_attention_in_scope','scope = self._resolve_clinical_scope(actor_id=actor_id, actor_roles=actor_roles)\nself._access.ensure_attention(entity, scope, actor_id=actor_id)')
delegate(p,cls,'_ensure_patient_in_scope','scope = self._resolve_clinical_scope(actor_id=actor_id, actor_roles=actor_roles)\nself._access.ensure_patient(patient_id, scope)\nreturn scope')
delegate(p,cls,'_resolve_clinical_scope','return self._access.attention_scope(actor_id=actor_id, actor_roles=actor_roles)')
p='app/services/patient.py';cls='PatientService'
delegate(p,cls,'_resolve_professional_scope','return self._access.patient_scope(actor_id=actor_id, actor_roles=actor_roles)')
delegate(p,cls,'_ensure_patient_in_scope','scope = self._resolve_professional_scope(actor_id=actor_id, actor_roles=actor_roles)\nself._access.ensure_patient(patient_id, scope)')
delegate('app/services/document.py','DocumentService','_ensure_actor_can_operate_attention','self._access.ensure_document_emitter(\n    attention_professional_id, actor_id=actor_id, actor_roles=actor_roles,\n)')

p='app/services/discovery.py'
s=source(p)
a=s.index('    """Resolve the only two clinical visibility modes')
b=s.index('\n\n\nclass PatientDiscoveryService:',a)
s=s[:a]+'''    return ClinicalAccessService.search_professional(
        actor_roles=actor_roles,
        professional_id=active_professional_id_for_user,
        allow_administrator=allow_administrator,
    )'''+s[b:]
s=s.replace('from app.exceptions import AuthorizationError','from app.services.clinical_access import ClinicalAccessService')
write(p,s)

for module,classes in [('patient',['PatientRepository']),('attention',['AttentionRepository']),('document',['DocumentRepository']),('discovery',['PatientDiscoveryRepository','AttentionDiscoveryRepository'])]:
    p=f'app/repositories/{module}.py'
    s=source(p).replace('from sqlalchemy.orm import ', 'from app.repositories.clinical_access import ClinicalAccessRepository\nfrom sqlalchemy.orm import ',1)
    write(p,s)
    for cls in classes:
        name='active_professional_id_for_user' if module=='discovery' else 'get_active_professional_id_for_user'
        delegate(p,cls,name,'return ClinicalAccessRepository(self._session).professional_id(user_id)')
        if module=='discovery':
            delegate(p,cls,'active_establishment_ids_for_professional','return sorted(ClinicalAccessRepository(self._session).establishment_ids(professional_id))')
        elif module=='patient':
            delegate(p,cls,'get_active_establishment_ids_for_professional','return ClinicalAccessRepository(self._session).establishment_ids(professional_id, on_date=on_date)')
