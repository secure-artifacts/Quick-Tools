import os
import json
import datetime

class ProjectManager:
    """
    Manage projects within a specific root directory.
    Metadata is stored in 'projects.json' inside that directory.
    """
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.data_file = os.path.join(root_dir, "projects.json") if root_dir else None
        self.projects = []
        self.reload()

    def set_root_dir(self, root_dir):
        self.root_dir = root_dir
        self.data_file = os.path.join(root_dir, "projects.json") if root_dir else None
        self.reload()

    def reload(self):
        self.projects = []
        if self.data_file and os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.projects = data.get("projects", [])
            except Exception:
                pass # Fail silently or log error
    
    def save(self):
        if not self.data_file:
            return
            
        data = {
            "projects": self.projects,
            "updated_at": str(datetime.datetime.now())
        }
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving projects: {e}")

    def add_project(self, name, description=""):
        """
        Add a new project or update existing one's timestamp.
        """
        # Check if exists
        for p in self.projects:
            if p["name"] == name:
                p["updated_at"] = str(datetime.datetime.now())
                self.save()
                return

        new_project = {
            "name": name,
            "created_at": str(datetime.datetime.now()),
            "updated_at": str(datetime.datetime.now()),
            "description": description
        }
        self.projects.append(new_project)
        self.save()

    def get_projects(self):
        return self.projects

    def get_project_path(self, project_name):
        if not self.root_dir:
            return None
        return os.path.join(self.root_dir, project_name)

    def get_project_files(self, project_name):
        """
        List files in the project subdirectory.
        """
        path = self.get_project_path(project_name)
        if not path or not os.path.exists(path):
            return []
        
        files = []
        try:
            for f in os.listdir(path):
                full_path = os.path.join(path, f)
                if os.path.isfile(full_path):
                    size = os.path.getsize(full_path)
                    files.append({
                        "name": f,
                        "path": full_path,
                        "size": size,
                        "ext": os.path.splitext(f)[1]
                    })
        except Exception:
            pass
        return files
