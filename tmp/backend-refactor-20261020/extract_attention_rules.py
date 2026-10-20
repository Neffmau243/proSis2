import ast
import textwrap
from refactor_tools import source, method, replace_method, imports, write

path = 'app/services/attention.py'
names = ['_assessment', '_add_nutritional_snapshot', '_validate_nutrition_record', '_validate_measurements']
methods = '\n'.join(method(path, 'AttentionService', name) for name in names)
for name in names:
    methods = methods.replace('def '+name+'(', 'def '+name.lstrip('_')+'(')
write('app/services/nutrition_assessment.py', '''"""Shared preview, nutritional validation and evaluation construction.

Uses the enclosing encounter transaction; never commits or rolls it back.
"""\n\n''' + imports(path).replace('from app.services.attention_context import AttentionContextLoader\n', '') + '''

class NutritionAssessmentService:
    def __init__(self, attentions: AttentionRepository, clinical_protocol: ClinicalProtocolValidator):
        self._attentions = attentions
        self._clinical_protocol = clinical_protocol

''' + methods)

# Preserve the facade's private adapters used by existing unit callers.
for name, call in {
    '_assessment': 'return self._nutrition.assessment(indicators, patient, measured_on, weight, height, scope)',
    '_add_nutritional_snapshot': 'self._nutrition.add_nutritional_snapshot(entity, command, age, indicators)',
    '_validate_nutrition_record': 'NutritionAssessmentService.validate_nutrition_record(command, birth_date, age)',
    '_validate_measurements': 'self._nutrition.validate_measurements(values, age_in_months)',
}.items():
    old = method(path, 'AttentionService', name)
    fn = ast.parse(textwrap.dedent(old)).body[0]
    header = '\n'.join(old.splitlines()[:fn.body[0].lineno-1])
    replace_method(path, 'AttentionService', name, header+'\n        '+call+'\n')

# Clinical context validation uses the same repository and exact rule order.
context = method(path, 'AttentionService', '_validate_clinical_context')
write('app/services/attention_validation.py', '"""Clinical assignment and catalog validation for a new encounter."""\n\n' + imports(path) + '''

class AttentionContextValidator:
    def __init__(self, attentions: AttentionRepository):
        self._attentions = attentions

''' + context.replace('def _validate_clinical_context(', 'def validate('))
replace_method(path, 'AttentionService', '_validate_clinical_context', '''    def _validate_clinical_context(self, command: AttentionCreate) -> None:
        AttentionContextValidator(self._attentions).validate(command)
''')

# Move only command-to-entity projection. Assessment remains calculated before it.
text = source(path)
tree = ast.parse(text)
service = next(n for n in tree.body if isinstance(n, ast.ClassDef))
create = next(n for n in service.body if isinstance(n, ast.FunctionDef) and n.name == 'create')
assign = next(n for n in ast.walk(create) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == 'Attention')
constructor = ast.get_source_segment(text, assign.value)
constructor = textwrap.dedent('            '+constructor)
constructor = constructor.replace('age_group.codigo', 'age_group_code')
constructor = constructor.replace('self._format_indicator(', 'format_indicator(')
start = constructor.index('valoracion_calculada=self._assessment(')
end = constructor.index('hora_inicio=', start)
constructor = constructor[:start] + 'valoracion_calculada=assessment.model_dump(mode="json"),\n    ' + constructor[end:]
mapper = source('app/mappers/attention.py')
mapper += '''

def attention_from_command(command, patient, age, age_group_code, indicators, assessment, actor_id) -> Attention:
    """Map validated values; no reads, writes or clinical decisions happen here."""
    return ''' + constructor + '\n'
mapper += '''

def format_indicator(value):
    return f"{value:.3f}" if value is not None else None
'''
write('app/mappers/attention.py', mapper)
lines = text.splitlines(keepends=True)
text = ''.join(lines[:assign.lineno-1]) + '''            assessment = self._assessment(
                indicators, patient, attention_date, command.peso_kg, command.talla_cm, scope
            )
            entity = attention_from_command(
                command, patient, age, age_group.codigo, indicators, assessment, actor_id
            )
''' + ''.join(lines[assign.end_lineno:])
text = text.replace('from app.mappers.attention import attention_to_response', 'from app.mappers.attention import attention_to_response, attention_from_command')
text = text.replace('from app.services.age_group import AgeGroupService', '''from app.services.age_group_resolver import AgeGroupResolver
from app.services.nutrition_assessment import NutritionAssessmentService
from app.services.attention_validation import AttentionContextValidator''')
text = text.replace('self._age_groups = AgeGroupService(session)', 'self._age_groups = AgeGroupResolver(AgeGroupRepository(session))')
text = text.replace('from app.repositories.attention import AttentionRepository', 'from app.repositories.attention import AttentionRepository\nfrom app.repositories.age_group import AgeGroupRepository')
text += '''
    @property
    def _nutrition(self) -> NutritionAssessmentService:
        return NutritionAssessmentService(self._attentions, self._clinical_protocol)
'''
write(path, text)
replace_method(path, 'AttentionService', '_format_indicator', '')

agepath = 'app/services/age_group.py'
resolve = method(agepath, 'AgeGroupService', 'resolve')
write('app/services/age_group_resolver.py', '''"""Read-only age-group resolution, separate from administrative configuration."""

from app.exceptions import BusinessRuleError
from app.models.catalog import AgeGroup
from app.repositories.age_group import AgeGroupRepository


class AgeGroupResolver:
    def __init__(self, repository: AgeGroupRepository) -> None:
        self._repository = repository

''' + resolve)
replace_method(agepath, 'AgeGroupService', 'resolve', '''    def resolve(self, age_in_months: int) -> AgeGroup:
        return AgeGroupResolver(self._repository).resolve(age_in_months)
''')
write(agepath, source(agepath).replace('from app.repositories.age_group import AgeGroupRepository', 'from app.repositories.age_group import AgeGroupRepository\nfrom app.services.age_group_resolver import AgeGroupResolver'))
