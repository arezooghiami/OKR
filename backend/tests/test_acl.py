from app.services.acl import RoleGrant, Scope, decide

TREE = {"it": "ceo", "fin": "ceo", "buy": "fin", "ceo": None}


def is_desc(u, anc):
    while u := TREE.get(u):
        if u == anc:
            return True
    return False


def manager(units):
    return RoleGrant("مدیر واحد", {("key_result", "edit"): "allow"}, {"key_result": Scope.UNIT_TREE}, set(units))


def test_allow_in_own_unit():
    assert decide([manager({"it"})], "key_result", "edit", "it", is_desc).allowed


def test_tree_scope_includes_descendants():
    assert decide([manager({"fin"})], "key_result", "edit", "buy", is_desc).allowed


def test_out_of_scope():
    d = decide([manager({"it"})], "key_result", "edit", "fin", is_desc)
    assert not d.allowed and d.rule == "out_of_scope"


def test_undefined_is_denied():
    d = decide([manager({"it"})], "key_result", "delete", "it", is_desc)
    assert not d.allowed and d.rule == "none"


def test_deny_beats_allow_across_roles():
    deny = RoleGrant("ناظر", {("key_result", "edit"): "deny"}, {}, set())
    d = decide([manager({"it"}), deny], "key_result", "edit", "it", is_desc)
    assert not d.allowed and d.rule == "deny"


def test_union_of_roles():
    viewer = RoleGrant("ناظر", {("key_result", "view"): "allow"}, {"key_result": Scope.ALL}, set())
    assert decide([viewer, manager({"it"})], "key_result", "view", "fin", is_desc).allowed
    assert decide([viewer, manager({"it"})], "key_result", "edit", "it", is_desc).allowed


def test_no_grants():
    assert not decide([], "key_result", "view", "it", is_desc).allowed
