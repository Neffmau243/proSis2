import ast
from refactor_tools import source, method, replace_method, imports, write

path = 'app/services/patient.py'
original = source(path)
groups = {
    'PatientDataRules': ['_validate_patient_catalogs', '_validate_family_history', '_validate_patient_residence', '_normalize_patient_locality', '_validate_document_number', '_validate_insurance_affiliation', '_validate_sis_and_ethnicity', '_validate_changed_patient_catalogs', '_ensure_document_is_available', '_require_active_document_type', '_raise_unavailable_catalog', '_validate_birth_and_registration_dates'],
    'PatientResponsibleRules': ['_validate_new_responsibles', '_validate_responsible', '_validate_responsible_update', '_ensure_active_principal_limit', '_ensure_minor_has_active_responsible', '_is_minor'],
    'PatientRiskRules': ['_validate_new_risks', '_validate_followup_fields', '_risk_origin', '_validate_risk_dates', '_ensure_risk_does_not_overlap', '_require_active_risk_group', '_periods_overlap'],
}
modules = {'PatientDataRules': 'patient_data', 'PatientResponsibleRules': 'patient_responsible', 'PatientRiskRules': 'patient_risk'}
constructors = {
    'PatientDataRules': '''    def __init__(self, repository: PatientRepository, today_provider: Callable[[], date]) -> None:
        self._repository = repository
        self._today_provider = today_provider
''',
    'PatientResponsibleRules': '''    def __init__(self, data_rules: PatientDataRules, today_provider: Callable[[], date]) -> None:
        self._data = data_rules
        self._today_provider = today_provider
''',
    'PatientRiskRules': '''    def __init__(self, repository: PatientRepository, origin_reader: AttentionOriginReader) -> None:
        self._repository = repository
        self._origin_reader = origin_reader
''',
}
for cls, names in groups.items():
    methods = '\n'.join(method(path, 'PatientService', name) for name in names)
    for name in names:
        methods = methods.replace('def '+name+'(', 'def '+name.lstrip('_')+'(')
        methods = methods.replace('self.'+name+'(', 'self.'+name.lstrip('_')+'(')
    methods = methods.replace('self._require_active_document_type(', 'self._data.require_active_document_type(')
    methods = methods.replace('self._raise_unavailable_catalog(', 'PatientDataRules.raise_unavailable_catalog(')
    methods = methods.replace('        from app.services.attention import AttentionService\n\n', '')
    methods = methods.replace('AttentionService(self._session).get(', 'self._origin_reader.get(')
    extra = ''
    if cls != 'PatientDataRules':
        extra += '\nfrom app.services.patient_data import PatientDataRules\n'
    if cls == 'PatientRiskRules':
        extra += 'from app.services.attention_origin import AttentionOriginReader\n'
    # Imports copied first, then unused imports removed by Ruff. No bodies are rewritten.
    write('app/services/'+modules[cls]+'.py', f'"""{cls}: validation only; transaction ownership remains in PatientService."""\n\n' + imports(path) + extra + '\n\nclass '+cls+':\n' + constructors[cls]+'\n'+methods)

for names in groups.values():
    for name in names:
        replace_method(path, 'PatientService', name, '')
text = source(path)
attrs = {'PatientDataRules': '_data_rules', 'PatientResponsibleRules': '_responsible_rules', 'PatientRiskRules': '_risk_rules'}
for cls, names in groups.items():
    for name in names:
        text = text.replace('self.'+name+'(', 'self.'+attrs[cls]+'.'+name.lstrip('_')+'(')
text += '''
    @property
    def _data_rules(self) -> PatientDataRules:
        return PatientDataRules(self._repository, self._today_provider)

    @property
    def _responsible_rules(self) -> PatientResponsibleRules:
        return PatientResponsibleRules(self._data_rules, self._today_provider)

    @property
    def _risk_rules(self) -> PatientRiskRules:
        return PatientRiskRules(self._repository, AttentionOriginReader(self._session))
'''
text = text.replace('from app.services.clinical_access import ClinicalAccessService', '''from app.services.clinical_access import ClinicalAccessService
from app.services.attention_origin import AttentionOriginReader
from app.services.patient_data import PatientDataRules
from app.services.patient_responsible import PatientResponsibleRules
from app.services.patient_risk import PatientRiskRules''')
write(path, text)
