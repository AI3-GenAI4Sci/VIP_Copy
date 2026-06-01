from seers_harness.intake import features
from seers_harness.intake.fields import REQUEST_ID_FIELDS, USER_PROFILE_FIELDS


def test_features_reexports_intake_field_constants_for_existing_callers():
    assert features.REQUEST_ID_FIELDS == REQUEST_ID_FIELDS
    assert features.USER_PROFILE_FIELDS == USER_PROFILE_FIELDS
