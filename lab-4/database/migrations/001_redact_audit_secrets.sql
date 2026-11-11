BEGIN;
CREATE OR REPLACE FUNCTION bookstore.audit_data_change() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,bookstore AS $$
DECLARE v_old JSONB; v_new JSONB; v_key JSONB:='{}'::JSONB; v_column TEXT;
        v_user_id BIGINT; v_username TEXT;
BEGIN
    IF TG_OP<>'INSERT' THEN v_old:=to_jsonb(OLD)-'password_hash'-'api_key_hash'-'api_token_hash'; END IF;
    IF TG_OP<>'DELETE' THEN v_new:=to_jsonb(NEW)-'password_hash'-'api_key_hash'-'api_token_hash'; END IF;
    FOREACH v_column IN ARRAY TG_ARGV LOOP
        v_key:=v_key||jsonb_build_object(v_column,COALESCE(v_new->v_column,v_old->v_column));
    END LOOP;
    v_user_id:=NULLIF(current_setting('app.user_id',TRUE),'')::BIGINT;
    v_username:=COALESCE(NULLIF(current_setting('app.username',TRUE),''),session_user);
    INSERT INTO bookstore.activity_log(user_id,username,action,table_name,record_key,old_data,new_data)
    VALUES(v_user_id,v_username,TG_OP,TG_TABLE_NAME,v_key,v_old,v_new);
    RETURN NULL;
END $$;
-- Оновлення функції захищає нові події; цей запит також очищує вже збережені знімки.
UPDATE bookstore.activity_log
SET old_data=old_data-'password_hash'-'api_token_hash'-'api_key_hash',
    new_data=new_data-'password_hash'-'api_token_hash'-'api_key_hash'
WHERE old_data ?| ARRAY['password_hash','api_token_hash','api_key_hash']
   OR new_data ?| ARRAY['password_hash','api_token_hash','api_key_hash'];
COMMIT;
