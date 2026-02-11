import os

try:
    LEADERSHIP_PROGRAM = os.getenv("LEADERSHIP_PROGRAM",None)
    BENEFITS = os.getenv("BENEFITS",None)
    BENEFITSFORM = os.getenv("BENEFITSFORM",None)
    JOB_DESCRIPTION = os.getenv("JOB_DESCRIPTION",None)
    ARTICLE = os.getenv("ARTICLE",None)
    CONTRIBUTE_RESOURCE = os.getenv("CONTRIBUTE_RESOURCE",None)
    LINK = os.getenv("LINK",None)
    EMPLOYEE_HANDBOOK = os.getenv("EMPLOYEE_HANDBOOK",None)
    IT_SECURITY_POLICY = os.getenv("IT_SECURITY_POLICY",None)
    IT_SECURITY_POLICY_STATISTICS = os.getenv("IT_SECURITY_POLICY_STATISTICS",None)
    POLICIES = os.getenv("POLICIES",None)
    POLICIES_VERSION = os.getenv("POLICIES_VERSION",None)
    USER_ACCEPTACE = os.getenv("USER_ACCEPTACE",None)
    VERSION_HISTORY = os.getenv("VERSION_HISTORY",None)

    MONGO_DEFAULT_URL = os.getenv("MONGO_DEFAULT_URL")
    MONGO_DATA_URL = os.getenv("MONGO_DATA_URL")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME")
    OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD")
    INDEX_NAME = os.getenv("INDEX_NAME","marketing_toolkit")
    OPENSEARCH_URL = os.getenv("OPENSEARCH_URL")

except Exception as e:
    raise EnvironmentError(f"Missing required environment variable: {e}")
