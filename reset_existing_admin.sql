-- Optional: remove the previously registered admin account so you can create it again.
-- Run this in Neon Console -> SQL Editor. Review the email before running.
BEGIN;
DO $$
DECLARE target_user_id INTEGER;
BEGIN
    SELECT id INTO target_user_id
    FROM users
    WHERE lower(email) = lower('samodas@vidullanka.com')
      AND role = 'admin'
    LIMIT 1;

    IF target_user_id IS NOT NULL THEN
        DELETE FROM winners WHERE selected_by = target_user_id;
        DELETE FROM artwork_marks WHERE teacher_id = target_user_id;
        DELETE FROM artworks WHERE uploaded_by = target_user_id;
        DELETE FROM users WHERE id = target_user_id;
    END IF;
END $$;
COMMIT;
