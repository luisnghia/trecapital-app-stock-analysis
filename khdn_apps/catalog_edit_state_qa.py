from khdn_apps.catalog_edit_state_patch import _sync, _stage_defaults, _category_defaults


def main():
    state={}
    stage1={"id":1,"name":"Đang tiếp cận khách hàng","sort_order":1,"sla_hours":24,"is_completion":0,"active":1}
    stage2={"id":2,"name":"Khách hàng đã cung cấp hồ sơ","sort_order":3,"sla_hours":48,"is_completion":0,"active":1}
    mapping={"name":"name","order":"order","sla":"sla","done":"done","active":"active"}
    assert _sync(state,"marker",mapping,stage1,_stage_defaults(stage1,8))
    assert state["name"]==stage1["name"] and state["sla"]==24.0
    # Simulate the user typing. Ordinary reruns on the same selected record must preserve edits.
    state["name"]="Tên đã sửa nhưng chưa lưu"
    assert not _sync(state,"marker",mapping,stage1,_stage_defaults(stage1,8))
    assert state["name"]=="Tên đã sửa nhưng chưa lưu"
    # Selecting another record must load the newly selected row.
    assert _sync(state,"marker",mapping,stage2,_stage_defaults(stage2,8))
    assert state["name"]==stage2["name"] and state["order"]==3 and state["sla"]==48.0
    # Returning to Create New clears old row values.
    assert _sync(state,"marker",mapping,None,_stage_defaults(None,8))
    assert state["name"]=="" and state["order"]==9 and state["sla"]==48.0

    cat1={"id":7,"name":"Hạn mức trọng điểm","description":"Theo dõi ưu tiên","sort_order":2,"active":1}
    cmap={"name":"cname","description":"desc","order":"corder","active":"cactive"}
    assert _sync(state,"cmarker",cmap,cat1,_category_defaults(cat1,3))
    assert state["cname"]=="Hạn mức trọng điểm" and state["desc"]=="Theo dõi ưu tiên"
    state["desc"]="Nội dung đang sửa"
    assert not _sync(state,"cmarker",cmap,cat1,_category_defaults(cat1,3))
    assert state["desc"]=="Nội dung đang sửa"
    assert _sync(state,"cmarker",cmap,None,_category_defaults(None,3))
    assert state["cname"]=="" and state["desc"]=="" and state["corder"]==4
    print("CATALOG_EDIT_STATE_QA_PASS")


if __name__=="__main__":
    main()
