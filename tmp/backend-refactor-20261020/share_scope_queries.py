from refactor_tools import source, write

path = 'app/repositories/attention.py'
text = source(path)
start = '''            visibility = [
                Attention.profesional_id == professional_id,
                recorded_referral(professional_id),
            ]
            if establishment_ids:
                visibility.append(Attention.establecimiento_id.in_(establishment_ids))
            statement = statement.where(or_(*visibility))'''
assert text.count(start) == 2
text = text.replace(start, '            statement = statement.where(attention_visibility(professional_id, establishment_ids))')
text = text.replace('from app.repositories.attention_scope import recorded_referral', 'from app.repositories.attention_scope import attention_visibility')
write(path, text)

path = 'app/repositories/discovery.py'
text = source(path)
begin = text.index('            # A professional may discover')
end = text.index('\n\n        statement = select(Patient)', begin)
text = text[:begin] + '            conditions.append(patient_visibility(professional_id, establishment_ids))' + text[end:]
start = start.replace('statement = statement.where(or_(*visibility))', 'conditions.append(or_(*visibility))')
assert start in text
text = text.replace(start, '            conditions.append(attention_visibility(professional_id, establishment_ids))')
text = text.replace('from app.repositories.attention_scope import recorded_referral', 'from app.repositories.attention_scope import attention_visibility, patient_visibility')
write(path, text)

path = 'app/repositories/patient.py'
text = source(path)
begin = text.index('        care_relationship = (')
end = text.index('        return self._session.scalar(statement) is not None', begin)
text = text[:begin] + '''        statement = select(Patient.id).where(
            Patient.id == patient_id,
            Patient.estado.is_(True),
            patient_visibility(professional_id, establishment_ids),
        )
''' + text[end:]
text = text.replace('from app.repositories.attention_scope import recorded_referral', 'from app.repositories.attention_scope import patient_visibility')
write(path, text)
