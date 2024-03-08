from farconf.config_ops import Atom, config_diff, config_merge


def test_merge_atom():
    assert config_merge(2, 3) == 3
    assert config_merge({"a": 2}, 4) == 4
    assert config_merge({"a": 2}, [2, 3]) == [2, 3]
    assert config_merge({"a": 2}, Atom({"b": 2})) == {"b": 2}

    assert config_merge("abc", "c") == "c"
    assert config_merge(["a", "b", "c"], "c") == "c"


def test_merge_is_leaf():
    def is_b_dict(d):
        return isinstance(d, dict) and "b" in d

    assert config_merge([{"a": 2}, 2], [{"b": 3}], is_leaf=lambda x, _: is_b_dict(x)) == [{"a": 2, "b": 3}, 2]
    assert config_merge([{"a": 2}, 2], [{"b": 3}], is_leaf=lambda _, y: is_b_dict(y)) == [{"b": 3}, 2]


def test_merge_lists():
    assert config_merge([2, 3], [4, 5, 6]) == [4, 5, 6]
    assert config_merge([2, 3], [4]) == [4, 3]
    assert config_merge([2, 3], [{"a": 2}]) == [{"a": 2}, 3]
    assert config_merge([{"b": 5}, 3], [{"a": 2}]) == [{"a": 2, "b": 5}, 3]


def test_that_atoms_dont_stack():
    assert config_merge(2, Atom(Atom(3))) == Atom(3)


def test_merge_dicts():
    assert config_merge({"a": 2, "b": 3}, {"a": 4}) == {"a": 4, "b": 3}


## BEGIN Claude-written tests
def test_merge_nested_dicts_and_lists():
    assert config_merge({"a": {"b": [1, 2]}, "c": 3}, {"a": {"b": [4, 5], "d": 6}}) == {"a": {"b": [4, 5], "d": 6}, "c": 3}


def test_merge_empty_dicts_and_lists():
    assert config_merge({}, {"a": 1}) == {"a": 1}
    assert config_merge({"a": 1}, {}) == {"a": 1}
    assert config_merge([], [1, 2]) == [1, 2]
    assert config_merge([1, 2], []) == [1, 2]


def test_merge_with_custom_is_leaf_key_check():
    def is_leaf_with_key(_, d):
        return isinstance(d, dict) and "key" in d

    assert config_merge({"a": {"b": 1}}, {"a": {"key": 2}}, is_leaf=is_leaf_with_key) == {"a": {"key": 2}}


def test_merge_lists_with_different_element_types():
    assert config_merge([1, "two"], [3, {"a": 4}]) == [3, {"a": 4}]


def test_merge_lists_of_lists():
    assert config_merge([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[5, 6], [7, 8]]


def test_merge_dicts_with_nested_atoms():
    assert config_merge({"a": {"b": Atom(1)}}, {"a": {"b": Atom(2), "c": 3}}) == {"a": {"b": 2, "c": 3}}


def test_merge_dicts_with_none_values():
    assert config_merge({"a": None, "b": 2}, {"a": 1, "c": None}) == {"a": 1, "b": 2, "c": None}


def test_merge_lists_with_none_values():
    assert config_merge([None, 2], [1, None]) == [1, None]


## END Claude-written tests


## BEGIN tests written by Claude and then edited
def test_diff_atom():
    assert config_diff(2, 3) == 3
    assert config_diff({"a": 2}, 4) == 4
    assert config_diff({"a": 2}, [2, 3]) == [2, 3]
    assert config_diff({"a": 2}, Atom({"b": 2})) == Atom({"b": 2})

    assert config_diff("abc", "c") == "c"
    assert config_diff(["a", "b", "c"], "c") == "c"


def test_diff_is_leaf():
    def is_b_dict(d):
        return isinstance(d, dict) and "b" in d

    assert config_diff([{"a": 2}, 2], [{"b": 3}], is_leaf=lambda x, _: is_b_dict(x)) == Atom([{"b": 3}])
    assert config_diff([{"a": 2}, 2], [{"b": 3}], is_leaf=lambda _, y: is_b_dict(y)) == Atom([{"b": 3}])

    assert config_diff([{"a": 2}], [{"b": 3}, 2], is_leaf=lambda _, y: is_b_dict(y)) == [Atom({"b": 3}), 2]

    assert config_diff([{"a": 2}], [{"a": 4, "b": 3}, 2]) == [{"a": 4, "b": 3}, 2]
    assert config_diff([{"a": 2}], [{"a": 4, "b": 3}, 2], is_leaf=lambda _, y: is_b_dict(y)) == [Atom({"a": 4, "b": 3}), 2]

    assert config_diff([{"b": 2}], [{"a": 4, "b": 3}, 2]) == [{"a": 4, "b": 3}, 2]
    assert config_diff([{"b": 2}], [{"a": 4, "b": 3}, 2], is_leaf=lambda x, _: is_b_dict(x)) == [Atom({"a": 4, "b": 3}), 2]


def test_diff_is_leaf_list():
    def is_len_2(_, y):
        return len(y) == 2

    assert config_diff([2, 3], [1, 3], is_leaf=is_len_2) == Atom([1, 3])


def test_diff_shorter_than_either_list():
    assert config_diff([2, 3], [4, 3]) == [4]
    assert config_diff([2, 3], [4, Atom(3)]) == [4, Atom(3)]

    assert config_diff([2, 3], [2, 3]) == []
    assert config_diff([2, 3], Atom([2, 3])) == Atom([2, 3])


def test_diff_lists():
    assert config_diff([2, 3], [4, 5, 6]) == [4, 5, 6]
    assert config_diff([2, 3], [4]) == Atom([4])

    assert config_diff([2, 3], [{"a": 2}]) == Atom([{"a": 2}])


def test_diff_dicts():
    assert config_diff({"a": 4}, {"a": 2, "b": 3}) == {"a": 2, "b": 3}
    assert config_diff({"a": 4}, {"a": 4, "b": 3}) == {"b": 3}
    assert config_diff({"a": 2, "b": 3}, {"a": 4, "c": 5}) == Atom({"a": 4, "c": 5})


def test_diff_nested_dicts_and_lists():
    assert config_diff({"a": {"b": [1, 2]}, "c": 3}, {"a": {"b": [4, 5], "d": 6}, "c": 3}) == {"a": {"b": [4, 5], "d": 6}}


def test_diff_empty_dicts_and_lists():
    assert config_diff({}, {"a": 1}) == {"a": 1}
    assert config_diff({"a": 1}, {}) == Atom({})
    assert config_diff([], [1, 2]) == [1, 2]
    assert config_diff([1, 2], []) == Atom([])


def test_diff_with_custom_is_leaf_key_check():
    def is_leaf_with_key(_, d):
        return isinstance(d, dict) and "key" in d

    assert config_diff({"a": {"b": 1}}, {"a": {"key": 2}}, is_leaf=is_leaf_with_key) == {"a": Atom({"key": 2})}


def test_diff_lists_with_different_element_types():
    assert config_diff([1, "two"], [3, {"a": 4}]) == [3, {"a": 4}]


def test_diff_dicts_with_nested_atoms():
    assert config_diff({"a": {"b": Atom(1), "c": 3}}, {"a": {"b": Atom(2)}}) == {"a": Atom({"b": Atom(2)})}


def test_diff_lists_with_nested_atoms():
    assert config_diff([{"a": Atom(1), "b": 3}], [{"a": Atom(2)}]) == [Atom({"a": Atom(2)})]


def test_diff_lists_of_lists():
    assert config_diff([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[5, 6], [7, 8]]
    assert config_diff([[1, 2], [3, 4]], [[5, 2], [3, 4]]) == [[5]]
    assert config_diff([[1, 2], [3, 4], ["a", "b"]], [[5, 2], [3, 4], ["c", "b"]]) == [[5], [], ["c"]]


## END tests written by Claude and then edited
