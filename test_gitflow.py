# System imports
import tempfile
import unittest
from typing import Optional

# Third-party imports
import pytest
from git import Repo

# Cruise imports
import gitflow as gf


class GitRepoTestEnvironment:

    def setup_repo(self):
        # Create a temporary directory for the Git repository
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Repo.init(self.temp_dir.name)
        self.repo_path = self.temp_dir.name
        self.configure_repo()

    def configure_repo(self):
        """
        Implement this method to create the state of the repo
        """
        return

    def teardown_repo(self):
        if self.temp_dir is not None:
            self.temp_dir.cleanup()

    @pytest.fixture
    def git_repo(self):
        self.setup_repo()
        yield self
        self.teardown_repo()

    @property
    def dag(self) -> dict:
        if self.repo is None:
            return {}
        dag, _ = gf.build_git_dag(self.repo)
        return dag

    @property
    def roots(self) -> list:
        if self.repo is None:
            return []
        _, roots = gf.build_git_dag(self.repo)
        return roots


def create_dummy_file_and_add_to_repo(
    repo: Repo,
    file_path: str,
    content: str,
    commit_msg: Optional[str] = None,
):
    if commit_msg is None:
        commit_msg = f"Added {file_path} to the repository"
    with open(file_path, "w") as file:
        file.write(content)
    repo.index.add([file_path])
    repo.index.commit(commit_msg)


class GitRepoDepth2FeatureTree(GitRepoTestEnvironment):
    def configure_repo(self):
        """
        Configure the repository with a depth of 2 feature tree.
        """
        repo = self.repo
        file_path = f"{self.temp_dir.name}/file.txt"
        # Setup the initial Git environment
        create_dummy_file_and_add_to_repo(
            repo,
            file_path=file_path,
            content="Initial content",
            commit_msg="Initial commit on master",
        )

        # Create branches and commits
        master = repo.heads.master  # master branch
        file_path = f"{self.temp_dir.name}/fileA.txt"
        branch_a = repo.create_head("A", master.commit)
        repo.git.branch("A", "--set-upstream-to", "master")

        # Checkout branch A and make commits
        branch_a.checkout()
        create_dummy_file_and_add_to_repo(
            repo,
            file_path=file_path,
            content="\nContent on branch A",
            commit_msg="First commit on A",
        )
        create_dummy_file_and_add_to_repo(
            repo,
            file_path=file_path,
            content="\nNext content on branch A",
            commit_msg="Second commit on A",
        )
        branch_b = repo.create_head("B", branch_a.commit)
        repo.git.branch("B", "--set-upstream-to", "A")

        # Checkout branch B and make a commit
        branch_b.checkout()
        file_path = f"{self.temp_dir.name}/fileB.txt"
        create_dummy_file_and_add_to_repo(
            repo,
            file_path=file_path,
            content="\nContent on branch B",
            commit_msg="First commit on B",
        )


class GitRepoDepth2FeatureTreeWithUpdatedMaster(GitRepoDepth2FeatureTree):
    def configure_repo(self):
        """
        Configure the repository with a depth of 2 feature tree.
        Update the master branch so that branch A is several commits behind master.
        """
        super().configure_repo()
        repo = self.repo
        # Update master without updating child branches a and b.
        master = repo.heads.master  # master branch
        master.checkout()
        file_path = f"{self.temp_dir.name}/file2.txt"
        # Setup the initial Git environment
        create_dummy_file_and_add_to_repo(
            repo,
            file_path=file_path,
            content="New content on master",
            commit_msg="Updated master branch 1",
        )
        create_dummy_file_and_add_to_repo(
            repo,
            file_path=file_path,
            content="Another new content on master",
            commit_msg="Updated master branch 2",
        )


class GitRepoDepth2FeatureTreeWithUpdatedMasterWithRebaseConflict(GitRepoDepth2FeatureTree):
    def configure_repo(self):
        """
        Configure the repository with a depth of 2 feature tree.
        Update the master branch so that branch A is several commits behind master.
        Update the same file as other branches to create a rebase conflict between branch A and branch B.
        """
        super().configure_repo()
        repo = self.repo
        # Update master without updating child branches a and b.
        master = repo.heads.master  # master branch
        master.checkout()
        file_path = f"{self.temp_dir.name}/fileA.txt"
        # Setup the initial Git environment
        create_dummy_file_and_add_to_repo(
            repo,
            file_path=file_path,
            content="New content on master",
            commit_msg="Updated master branch 1",
        )
        create_dummy_file_and_add_to_repo(
            repo,
            file_path=file_path,
            content="Another new content on master",
            commit_msg="Updated master branch 2",
        )


class TestGitOperations(GitRepoDepth2FeatureTree):
    def test_depth_2_feature_tree_constructed(self, git_repo: GitRepoDepth2FeatureTree):
        # Example test method to identify commits
        # This is where you would call your script or function to test
        print("Running commit identification test")
        expected_roots = git_repo.roots
        expected_dag = git_repo.dag
        repo = git_repo.repo
        dag, roots = gf.build_git_dag(repo)
        assert expected_roots
        assert expected_dag
        assert roots == expected_roots
        assert dag == expected_dag
        gf.print_dag(dag, roots, repo, cascade=False, push_updates=False)


class TestGitOperationsWithUpdatedMaster(GitRepoDepth2FeatureTreeWithUpdatedMaster):
    def test_rebase_works_with_updated_master(
        self, git_repo: GitRepoDepth2FeatureTreeWithUpdatedMaster
    ):
        # Example test method to identify commits
        # This is where you would call your script or function to test
        print("Running test cascaded rebase.")
        expected_roots = git_repo.roots
        expected_dag = git_repo.dag
        repo = git_repo.repo
        dag, roots = gf.build_git_dag(repo)
        print(roots)
        print(dag)
        assert expected_roots
        assert expected_dag
        print(f"expected roots: {expected_roots}")
        print(expected_dag)
        assert roots == expected_roots
        assert dag == expected_dag
        print("Before rebase:")
        gf.print_dag(dag, roots, repo, cascade=False, push_updates=False)
        print("Start rebase:")
        gf.print_dag(dag, roots, repo, cascade=True, push_updates=False)
        print("After rebase:")
        gf.print_dag(dag, roots, repo, cascade=False, push_updates=False)

class TestGitOperationsWithRebaseConflict(GitRepoDepth2FeatureTreeWithUpdatedMasterWithRebaseConflict):
    def test_rebase_aborts_with_conflict(
        self, git_repo: GitRepoDepth2FeatureTreeWithUpdatedMaster
    ):
        # Example test method to identify commits
        # This is where you would call your script or function to test
        print("Running test cascaded rebase.")
        expected_roots = git_repo.roots
        expected_dag = git_repo.dag
        repo = git_repo.repo
        dag, roots = gf.build_git_dag(repo)
        print(roots)
        print(dag)
        assert expected_roots
        assert expected_dag
        print(f"expected roots: {expected_roots}")
        print(expected_dag)
        assert roots == expected_roots
        assert dag == expected_dag
        print("Before rebase:")
        gf.print_dag(dag, roots, repo, cascade=False, push_updates=False)
        print("Start rebase:")
        gf.print_dag(dag, roots, repo, cascade=True, push_updates=False)
        print("After rebase:")
        gf.print_dag(dag, roots, repo, cascade=False, push_updates=False)


if __name__ == "__main__":
    unittest.main()
