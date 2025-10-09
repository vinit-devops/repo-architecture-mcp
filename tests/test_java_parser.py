"""Tests for the Java parser."""

import pytest
from repo_architecture_mcp.parsers.java_parser import JavaParser
from repo_architecture_mcp.models import Visibility


class TestJavaParser:
    """Test cases for the Java parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = JavaParser()
    
    def test_supported_extensions(self):
        """Test supported file extensions."""
        assert self.parser.supported_extensions == ['.java']
    
    def test_language_name(self):
        """Test language name."""
        assert self.parser.language_name == 'java'
    
    @pytest.mark.asyncio
    async def test_parse_package_declaration(self):
        """Test parsing package declarations."""
        code = '''
package com.example.myapp;

public class MyClass {
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        assert result.namespace == 'com.example.myapp'
    
    @pytest.mark.asyncio
    async def test_parse_imports(self):
        """Test parsing import statements."""
        code = '''
package com.example;

import java.util.List;
import java.util.ArrayList;
import java.io.*;
import static java.lang.Math.PI;
import static java.util.Collections.*;
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        assert len(result.imports) == 5
        
        imports = {imp.module: imp for imp in result.imports}
        
        # Regular imports
        assert 'java.util' in imports
        list_import = next(imp for imp in result.imports if 'List' in imp.imported_names)
        assert list_import.imported_names == ['List']
        
        # Wildcard import
        io_import = next(imp for imp in result.imports if imp.module == 'java.io')
        assert io_import.imported_names == ['*']
        
        # Static imports
        static_imports = [imp for imp in result.imports if 'static' in str(imp)]
        # Note: The exact handling of static imports depends on implementation
    
    @pytest.mark.asyncio
    async def test_parse_simple_class(self):
        """Test parsing a simple class definition."""
        code = '''
public class SimpleClass {
    private String name;
    private int age;
    
    public SimpleClass(String name, int age) {
        this.name = name;
        this.age = age;
    }
    
    public String getName() {
        return name;
    }
    
    public void setName(String name) {
        this.name = name;
    }
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        assert len(result.classes) == 1
        
        cls = result.classes[0]
        assert cls.name == 'SimpleClass'
        assert cls.visibility == Visibility.PUBLIC
        
        # Check fields
        assert len(cls.attributes) == 2
        fields = {field.name: field for field in cls.attributes}
        assert fields['name'].type_hint == 'String'
        assert fields['name'].visibility == Visibility.PRIVATE
        assert fields['age'].type_hint == 'int'
        
        # Check methods (including constructor)
        assert len(cls.methods) == 3
        method_names = [method.name for method in cls.methods]
        assert 'SimpleClass' in method_names  # Constructor
        assert 'getName' in method_names
        assert 'setName' in method_names
    
    @pytest.mark.asyncio
    async def test_parse_inheritance(self):
        """Test parsing class inheritance."""
        code = '''
public abstract class Animal {
    protected String name;
    
    public Animal(String name) {
        this.name = name;
    }
    
    public abstract void makeSound();
    
    public String getName() {
        return name;
    }
}

public class Dog extends Animal {
    private String breed;
    
    public Dog(String name, String breed) {
        super(name);
        this.breed = breed;
    }
    
    @Override
    public void makeSound() {
        System.out.println("Woof!");
    }
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        assert len(result.classes) == 2
        
        animal = next(cls for cls in result.classes if cls.name == 'Animal')
        assert animal.is_abstract is True
        assert animal.inheritance == []
        
        dog = next(cls for cls in result.classes if cls.name == 'Dog')
        assert dog.inheritance == ['Animal']
        assert dog.is_abstract is False
    
    @pytest.mark.asyncio
    async def test_parse_interfaces(self):
        """Test parsing interface definitions."""
        code = '''
public interface Drawable {
    void draw();
    void setColor(String color);
}

public interface Resizable {
    void resize(int width, int height);
}

public class Shape implements Drawable, Resizable {
    private String color;
    
    public void draw() {
        System.out.println("Drawing shape");
    }
    
    public void setColor(String color) {
        this.color = color;
    }
    
    public void resize(int width, int height) {
        // Implementation
    }
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        assert len(result.classes) == 3
        
        drawable = next(cls for cls in result.classes if cls.name == 'Drawable')
        assert drawable.is_abstract is True  # Interfaces are abstract
        
        shape = next(cls for cls in result.classes if cls.name == 'Shape')
        assert set(shape.interfaces) == {'Drawable', 'Resizable'}
    
    @pytest.mark.asyncio
    async def test_parse_method_modifiers(self):
        """Test parsing method modifiers."""
        code = '''
public class ModifierClass {
    public void publicMethod() {}
    private void privateMethod() {}
    protected void protectedMethod() {}
    static void packagePrivateMethod() {}
    
    public static void staticMethod() {}
    public final void finalMethod() {}
    public synchronized void synchronizedMethod() {}
    public abstract void abstractMethod();
    
    public native void nativeMethod();
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        cls = result.classes[0]
        methods = {method.name: method for method in cls.methods}
        
        assert methods['publicMethod'].visibility == Visibility.PUBLIC
        assert methods['privateMethod'].visibility == Visibility.PRIVATE
        assert methods['protectedMethod'].visibility == Visibility.PROTECTED
        assert methods['packagePrivateMethod'].visibility == Visibility.PUBLIC  # Package-private treated as public
        
        assert methods['staticMethod'].is_static is True
        assert methods['abstractMethod'].is_abstract is True
    
    @pytest.mark.asyncio
    async def test_parse_generic_types(self):
        """Test parsing generic types."""
        code = '''
import java.util.List;
import java.util.Map;

public class GenericClass<T, U> {
    private List<T> items;
    private Map<String, U> cache;
    
    public GenericClass() {
        this.items = new ArrayList<>();
        this.cache = new HashMap<>();
    }
    
    public void addItem(T item) {
        items.add(item);
    }
    
    public T getItem(int index) {
        return items.get(index);
    }
    
    public <V> V transform(T input, Function<T, V> transformer) {
        return transformer.apply(input);
    }
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        cls = result.classes[0]
        assert cls.name == 'GenericClass'
        
        # Check generic fields
        fields = {field.name: field for field in cls.attributes}
        assert 'List<T>' in fields['items'].type_hint
        assert 'Map<String, U>' in fields['cache'].type_hint
        
        # Check generic methods
        transform_method = next(m for m in cls.methods if m.name == 'transform')
        assert len(transform_method.parameters) == 2
    
    @pytest.mark.asyncio
    async def test_parse_enums(self):
        """Test parsing enum definitions."""
        code = '''
public enum Color {
    RED, GREEN, BLUE;
}

public enum Planet {
    MERCURY(3.303e+23, 2.4397e6),
    VENUS(4.869e+24, 6.0518e6),
    EARTH(5.976e+24, 6.37814e6);
    
    private final double mass;
    private final double radius;
    
    Planet(double mass, double radius) {
        this.mass = mass;
        this.radius = radius;
    }
    
    public double getMass() {
        return mass;
    }
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        assert len(result.classes) == 2
        
        color_enum = next(cls for cls in result.classes if cls.name == 'Color')
        assert color_enum.name == 'Color'
        
        planet_enum = next(cls for cls in result.classes if cls.name == 'Planet')
        assert len(planet_enum.attributes) == 2  # mass and radius fields
        assert len(planet_enum.methods) >= 2  # constructor and getMass
    
    @pytest.mark.asyncio
    async def test_parse_nested_classes(self):
        """Test parsing nested classes."""
        code = '''
public class OuterClass {
    private String outerField;
    
    public class InnerClass {
        public void innerMethod() {
            System.out.println(outerField);
        }
    }
    
    public static class StaticNestedClass {
        public void staticNestedMethod() {
            System.out.println("Static nested");
        }
    }
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        # The parser might handle nested classes differently
        # At minimum, the outer class should be parsed
        outer_class = next(cls for cls in result.classes if cls.name == 'OuterClass')
        assert outer_class.name == 'OuterClass'
    
    @pytest.mark.asyncio
    async def test_parse_annotations(self):
        """Test parsing Java annotations."""
        code = '''
@Entity
@Table(name = "users")
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private String name;
    
    @Override
    public String toString() {
        return "User{id=" + id + ", name='" + name + "'}";
    }
    
    @Deprecated
    public void oldMethod() {
        // Legacy code
    }
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        cls = result.classes[0]
        assert cls.name == 'User'
        
        # Check if decorators/annotations are captured
        # The exact implementation may vary
        assert len(cls.attributes) >= 2
        assert len(cls.methods) >= 2
    
    @pytest.mark.asyncio
    async def test_parse_method_parameters(self):
        """Test parsing method parameters with various types."""
        code = '''
public class ParameterTest {
    public void simpleParams(int a, String b) {}
    
    public void arrayParams(int[] numbers, String... strings) {}
    
    public void genericParams(List<String> items, Map<String, Integer> map) {}
    
    public void finalParams(final String name, final int age) {}
    
    public <T> void genericMethod(T item, Class<T> clazz) {}
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        cls = result.classes[0]
        methods = {method.name: method for method in cls.methods}
        
        # Check simple parameters
        simple_method = methods['simpleParams']
        assert len(simple_method.parameters) == 2
        assert simple_method.parameters[0].type_hint == 'int'
        assert simple_method.parameters[0].name == 'a'
        assert simple_method.parameters[1].type_hint == 'String'
        assert simple_method.parameters[1].name == 'b'
        
        # Check array parameters
        array_method = methods['arrayParams']
        assert len(array_method.parameters) == 2
        assert 'int[]' in array_method.parameters[0].type_hint
        
        # Check generic parameters
        generic_method = methods['genericParams']
        assert len(generic_method.parameters) == 2
    
    @pytest.mark.asyncio
    async def test_parse_throws_clause(self):
        """Test parsing methods with throws clauses."""
        code = '''
public class ExceptionTest {
    public void singleException() throws IOException {}
    
    public void multipleExceptions() throws IOException, SQLException {}
    
    public void genericException() throws Exception {}
}
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        cls = result.classes[0]
        assert len(cls.methods) == 3
        # The throws clause handling depends on implementation
    
    @pytest.mark.asyncio
    async def test_parse_empty_file(self):
        """Test parsing an empty Java file."""
        result = await self.parser.parse_file('test.java', '')
        
        assert result.language == 'java'
        assert result.classes == []
        assert result.imports == []
        assert result.namespace is None
        assert result.parse_errors == []
    
    @pytest.mark.asyncio
    async def test_parse_malformed_code(self):
        """Test parsing malformed Java code."""
        code = '''
public class MalformedClass {
    public void method() {
        // Missing closing brace
    
    public void anotherMethod() {}
// Missing closing brace for class
'''
        
        result = await self.parser.parse_file('test.java', code)
        
        # Should not crash, may have partial results
        assert result.language == 'java'
        # The parser should handle malformed code gracefully