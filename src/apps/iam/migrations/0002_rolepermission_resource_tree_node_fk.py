from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("resource_tree", "0001_initial"),
        ("iam", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="rolepermission",
            old_name="resource_tree_node_id",
            new_name="resource_tree_node",
        ),
        migrations.AlterField(
            model_name="rolepermission",
            name="resource_tree_node",
            field=models.ForeignKey(
                db_column="resource_tree_node_id",
                help_text="资源树节点",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="role_permissions",
                to="resource_tree.resourcetreenode",
            ),
        ),
    ]

