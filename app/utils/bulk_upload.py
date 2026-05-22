import csv
import io
from datetime import datetime
from sqlalchemy import text
from app.database import engine

def fast_load_csv(file_path: str):
    """
    High-performance CSV bulk upload using PostgreSQL COPY command.
    Distributes 74 attributes across normalized tables: leads, companies, campaigns, etc.
    Handles lead_id PK conflicts using UPSERT logic.
    """
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()

        # 1. Create a temporary table for the 74-column staging area
        cursor.execute("DROP TABLE IF EXISTS temp_leads_load;")
        cursor.execute("""
            CREATE TEMPORARY TABLE temp_leads_load (
                id VARCHAR,
                first_name VARCHAR,
                last_name VARCHAR,
                name VARCHAR,
                email VARCHAR,
                domain VARCHAR,
                primary_phone VARCHAR,
                boardline_phone VARCHAR,
                status VARCHAR,
                notes TEXT,
                
                -- Campaign details
                campaign_name VARCHAR,
                campaign_description TEXT,
                campaign_status VARCHAR,
                
                -- Company details
                company_name VARCHAR,
                company_url VARCHAR,
                company_location VARCHAR,
                company_industry VARCHAR,
                company_employee_size VARCHAR,
                company_proof_links TEXT,
                
                -- Campaign Lookup details
                campaign_order_id VARCHAR,
                campaign_type VARCHAR,
                campaign_segment VARCHAR,
                campaign_asset_id VARCHAR,
                
                -- Person job details
                job_level VARCHAR,
                job_function VARCHAR,
                job_department VARCHAR,
                
                -- Intelligence (CQ1-CQ10)
                cq1 TEXT, cq2 TEXT, cq3 TEXT, cq4 TEXT, cq5 TEXT,
                cq6 TEXT, cq7 TEXT, cq8 TEXT, cq9 TEXT, cq10 TEXT,
                call_recording TEXT,
                agent_comments TEXT,
                
                -- Audit
                audit_primary_status VARCHAR,
                audit_secondary_status VARCHAR,
                audit_disposition VARCHAR,
                audit_comments TEXT,
                audit_by INTEGER,
                
                -- Billing
                billing_delivery_status VARCHAR,
                billing_packaged_by VARCHAR,
                billing_status VARCHAR,
                billing_date DATE,
                
                scored_by INTEGER,
                
                -- Total so far: 10 + 3 + 6 + 4 + 3 + 12 + 5 + 4 + 1 = 48 columns
                -- Filling up to 74 columns with placeholders
                col49 VARCHAR, col50 VARCHAR, col51 VARCHAR, col52 VARCHAR, col53 VARCHAR,
                col54 VARCHAR, col55 VARCHAR, col56 VARCHAR, col57 VARCHAR, col58 VARCHAR,
                col59 VARCHAR, col60 VARCHAR, col61 VARCHAR, col62 VARCHAR, col63 VARCHAR,
                col64 VARCHAR, col65 VARCHAR, col66 VARCHAR, col67 VARCHAR, col68 VARCHAR,
                col69 VARCHAR, col70 VARCHAR, col71 VARCHAR, col72 VARCHAR, col73 VARCHAR,
                col74 VARCHAR
            );
        """)

        # 2. Stream CSV file into the temporary table
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            cursor.copy_expert("COPY temp_leads_load FROM STDIN WITH CSV HEADER", f)

        # 3. Distribute data into normalized tables using SQL

        # Populate Companies
        cursor.execute("""
            INSERT INTO companies (name, url, location, industry, employee_size, proof_links)
            SELECT DISTINCT company_name, company_url, company_location, company_industry, company_employee_size, company_proof_links
            FROM temp_leads_load
            WHERE company_name IS NOT NULL
            ON CONFLICT (name) DO NOTHING;
        """)

        # Populate Campaigns (Consolidated)
        cursor.execute("""
            INSERT INTO campaigns (name, description, status, order_id, type, segment, asset_id, is_active, created_at)
            SELECT DISTINCT campaign_name, campaign_description, COALESCE(campaign_status, 'active'),
                            campaign_order_id, campaign_type, campaign_segment, campaign_asset_id,
                            TRUE, NOW()
            FROM temp_leads_load
            WHERE campaign_name IS NOT NULL
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                order_id = EXCLUDED.order_id,
                type = EXCLUDED.type,
                segment = EXCLUDED.segment,
                asset_id = EXCLUDED.asset_id;
        """)


        # Populate JobProfiles
        cursor.execute("""
            INSERT INTO job_profiles (level, function, department)
            SELECT DISTINCT job_level, job_function, job_department
            FROM temp_leads_load
            WHERE job_level IS NOT NULL OR job_function IS NOT NULL OR job_department IS NOT NULL
            ON CONFLICT (level, function, department) DO NOTHING;
        """)

        # Populate Leads with UPSERT (Flattened)
        # We join to get IDs for normalized references
        cursor.execute("""
            INSERT INTO leads (
                id, first_name, last_name, name, email, domain, primary_phone, boardline_phone,
                status, notes, 
                campaign_name, campaign_description, campaign_status,
                company_name, company_url, company_location, company_industry, company_employee_size, company_proof_links,
                campaign_order_id, campaign_type, campaign_segment, campaign_asset_id,
                job_level, job_function, job_department,
                campaign_id, scored_by, company_id, job_profile_id, 
                cq1, cq2, cq3, cq4, cq5, cq6, cq7, cq8, cq9, cq10, call_recording, agent_comments,
                audit_primary_status, audit_secondary_status, audit_disposition, audit_comments, audit_by,
                billing_delivery_status, billing_packaged_by, billing_status, billing_date,
                col49, col50, col51, col52, col53, col54, col55, col56, col57, col58,
                col59, col60, col61, col62, col63, col64, col65, col66, col67, col68,
                col69, col70, col71, col72, col73, col74,
                created_at
            )
            SELECT DISTINCT ON (t.email)
                CASE WHEN t.id ~ '^[0-9]+$' THEN t.id::INTEGER ELSE nextval('leads_id_seq') END,
                t.first_name, t.last_name, t.name, t.email, t.domain, t.primary_phone, t.boardline_phone,
                t.status, t.notes,
                t.campaign_name, t.campaign_description, t.campaign_status,
                t.company_name, t.company_url, t.company_location, t.company_industry, t.company_employee_size, t.company_proof_links,
                t.campaign_order_id, t.campaign_type, t.campaign_segment, t.campaign_asset_id,
                t.job_level, t.job_function, t.job_department,
                camp.id, t.scored_by, comp.id, jp.id,
                t.cq1, t.cq2, t.cq3, t.cq4, t.cq5, t.cq6, t.cq7, t.cq8, t.cq9, t.cq10, t.call_recording, t.agent_comments,
                t.audit_primary_status, t.audit_secondary_status, t.audit_disposition, t.audit_comments, t.audit_by,
                t.billing_delivery_status, t.billing_packaged_by, t.billing_status, t.billing_date,
                t.col49, t.col50, t.col51, t.col52, t.col53, t.col54, t.col55, t.col56, t.col57, t.col58,
                t.col59, t.col60, t.col61, t.col62, t.col63, t.col64, t.col65, t.col66, t.col67, t.col68,
                t.col69, t.col70, t.col71, t.col72, t.col73, t.col74,
                NOW()
            FROM temp_leads_load t
            LEFT JOIN companies comp ON t.company_name = comp.name
            LEFT JOIN campaigns camp ON t.campaign_name = camp.name
            LEFT JOIN job_profiles jp ON t.job_level = jp.level AND t.job_function = jp.function AND t.job_department = jp.department
            ORDER BY t.email, t.id DESC
            ON CONFLICT (email) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                domain = EXCLUDED.domain,
                primary_phone = EXCLUDED.primary_phone,
                boardline_phone = EXCLUDED.boardline_phone,
                status = EXCLUDED.status,
                notes = EXCLUDED.notes,
                campaign_id = EXCLUDED.campaign_id,
                scored_by = EXCLUDED.scored_by,
                company_id = EXCLUDED.company_id,
                job_profile_id = EXCLUDED.job_profile_id,
                campaign_name = EXCLUDED.campaign_name,
                campaign_description = EXCLUDED.campaign_description,
                campaign_status = EXCLUDED.campaign_status,
                company_name = EXCLUDED.company_name,
                company_url = EXCLUDED.company_url,
                company_location = EXCLUDED.company_location,
                company_industry = EXCLUDED.company_industry,
                company_employee_size = EXCLUDED.company_employee_size,
                company_proof_links = EXCLUDED.company_proof_links,
                campaign_order_id = EXCLUDED.campaign_order_id,
                campaign_type = EXCLUDED.campaign_type,
                campaign_segment = EXCLUDED.campaign_segment,
                campaign_asset_id = EXCLUDED.campaign_asset_id,
                job_level = EXCLUDED.job_level,
                job_function = EXCLUDED.job_function,
                job_department = EXCLUDED.job_department,
                cq1 = EXCLUDED.cq1, cq2 = EXCLUDED.cq2, cq3 = EXCLUDED.cq3, cq4 = EXCLUDED.cq4, cq5 = EXCLUDED.cq5,
                cq6 = EXCLUDED.cq6, cq7 = EXCLUDED.cq7, cq8 = EXCLUDED.cq8, cq9 = EXCLUDED.cq9, cq10 = EXCLUDED.cq10,
                call_recording = EXCLUDED.call_recording, agent_comments = EXCLUDED.agent_comments,
                audit_primary_status = EXCLUDED.audit_primary_status,
                audit_secondary_status = EXCLUDED.audit_secondary_status,
                audit_disposition = EXCLUDED.audit_disposition,
                audit_comments = EXCLUDED.audit_comments,
                audit_by = EXCLUDED.audit_by,
                billing_delivery_status = EXCLUDED.billing_delivery_status,
                billing_packaged_by = EXCLUDED.billing_packaged_by,
                billing_status = EXCLUDED.billing_status,
                billing_date = EXCLUDED.billing_date,
                col49 = EXCLUDED.col49, col50 = EXCLUDED.col50, col51 = EXCLUDED.col51,
                col52 = EXCLUDED.col52, col53 = EXCLUDED.col53, col54 = EXCLUDED.col54,
                col55 = EXCLUDED.col55, col56 = EXCLUDED.col56, col57 = EXCLUDED.col57,
                col58 = EXCLUDED.col58, col59 = EXCLUDED.col59, col60 = EXCLUDED.col60,
                col61 = EXCLUDED.col61, col62 = EXCLUDED.col62, col63 = EXCLUDED.col63,
                col64 = EXCLUDED.col64, col65 = EXCLUDED.col65, col66 = EXCLUDED.col66,
                col67 = EXCLUDED.col67, col68 = EXCLUDED.col68, col69 = EXCLUDED.col69,
                col70 = EXCLUDED.col70, col71 = EXCLUDED.col71, col72 = EXCLUDED.col72,
                col73 = EXCLUDED.col73, col74 = EXCLUDED.col74;
        """)

        # Return the count of rows processed
        cursor.execute("SELECT count(*) FROM temp_leads_load")
        total_rows = cursor.fetchone()[0]

        raw_conn.commit()
        return total_rows
    except Exception as e:
        raw_conn.rollback()
        raise e
    finally:
        raw_conn.close()

if __name__ == "__main__":
    # Example usage / test
    # fast_load_csv("leads_74_cols.csv")
    pass
